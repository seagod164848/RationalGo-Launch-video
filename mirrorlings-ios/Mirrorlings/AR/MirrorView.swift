import ARKit
import Combine
import RealityKit
import SwiftUI

/// The front camera, face tracking, and the 3D creature, in one ARView.
struct MirrorView: UIViewRepresentable {
    let game: GameModel

    func makeCoordinator() -> MirrorCoordinator { MirrorCoordinator(game: game) }

    func makeUIView(context: Context) -> ARView { context.coordinator.makeView() }

    func updateUIView(_ uiView: ARView, context: Context) {}

    static func dismantleUIView(_ uiView: ARView, coordinator: MirrorCoordinator) {
        uiView.session.pause()
        coordinator.updates?.cancel()
    }
}

final class MirrorCoordinator: NSObject, ARSessionDelegate {
    let game: GameModel
    weak var arView: ARView?
    var updates: Cancellable?

    private let stage = AnchorEntity(world: SIMD3<Float>(0, 0, 0))
    private var rig: CreatureRig?
    private var rigID: UUID?
    private var position = SIMD3<Float>(0, 0, 0)
    private var clock: Float = 0
    private var snapshotTaken = false
    private var flipCooldown: Float = 0

    init(game: GameModel) { self.game = game }

    func makeView() -> ARView {
        let view = ARView(frame: .zero, cameraMode: .ar, automaticallyConfigureSession: false)
        view.session.delegate = self
        view.scene.addAnchor(stage)

        let key = DirectionalLight()
        key.light.intensity = 2200
        key.orientation = simd_quatf(angle: -0.8, axis: SIMD3(1, 0, 0)) * simd_quatf(angle: 0.4, axis: SIMD3(0, 1, 0))
        stage.addChild(key)

        updates = view.scene.subscribe(to: SceneEvents.Update.self) { [weak self] event in
            self?.step(dt: event.deltaTime)
        }
        arView = view

        if ARFaceTrackingConfiguration.isSupported {
            let config = ARFaceTrackingConfiguration()
            config.maximumNumberOfTrackedFaces = min(2, ARFaceTrackingConfiguration.supportedNumberOfTrackedFaces)
            config.isLightEstimationEnabled = true
            view.session.run(config, options: [.resetTracking, .removeExistingAnchors])
        }
        return view
    }

    func session(_ session: ARSession, didFailWithError error: Error) {
        let message: String
        if let arError = error as? ARError, arError.code == .cameraUnauthorized {
            message = "Camera access is off. Turn it on in Settings → Mirrorlings → Camera."
        } else {
            message = "The mirror stopped working (\(error.localizedDescription)). Try again."
        }
        DispatchQueue.main.async { self.game.cameraFailed(message) }
    }

    // MARK: Per-frame

    private func step(dt: TimeInterval) {
        guard let view = arView, let frame = view.session.currentFrame else { return }
        clock += Float(dt)
        flipCooldown = max(0, flipCooldown - Float(dt))

        let camT = frame.camera.transform
        let camPos = SIMD3<Float>(camT.columns.3.x, camT.columns.3.y, camT.columns.3.z)
        let anchors = frame.anchors
            .compactMap { $0 as? ARFaceAnchor }
            .filter { $0.isTracked }
            .sorted { simd_distance(Self.origin($0.transform), camPos) < simd_distance(Self.origin($1.transform), camPos) }
        let faces = anchors.map { TrackedFace(shapes: Blendshapes($0.blendShapes), transform: $0.transform) }
        let ambient = frame.lightEstimate.map { Float($0.ambientIntensity) }

        game.tick(dt: dt, faces: faces, ambient: ambient)
        sync(view: view, dt: Float(dt), face: anchors.first?.transform, camT: camT, camPos: camPos)
    }

    private func sync(view: ARView, dt: Float, face: simd_float4x4?, camT: simd_float4x4, camPos: SIMD3<Float>) {
        guard let enc = game.encounter else {
            rig?.root.removeFromParent()
            rig = nil
            rigID = nil
            return
        }

        if rigID != enc.id {
            rig?.root.removeFromParent()
            let fresh = CreatureBuilder.make(enc.species, primary: enc.primary, secondary: enc.secondary)
            stage.addChild(fresh.root)
            rig = fresh
            rigID = enc.id
            snapshotTaken = false
            position = target(for: enc, face: face, camT: camT) + SIMD3(0, 0.12, 0)
        }
        guard let rig else { return }

        var goal = target(for: enc, face: face, camT: camT)
        if enc.state == .fleeing {
            let faceCenter = face.map(Self.origin) ?? goal
            var away = position - faceCenter
            away.y = 0
            let dir = simd_length(away) > 0.001 ? simd_normalize(away) : SIMD3<Float>(1, 0, 0)
            goal = position + dir * 0.35 + SIMD3(0, 0.05, 0)
        }
        let ease = 1 - powf(0.002, dt)
        position += (goal - position) * ease
        rig.root.position = position

        // Turn the creature's +Z toward the camera, staying upright against gravity.
        let forward = simd_normalize(camPos - position)
        var right = simd_cross(SIMD3<Float>(0, 1, 0), forward)
        right = simd_length(right) < 1e-4 ? SIMD3(1, 0, 0) : simd_normalize(right)
        let up = simd_cross(forward, right)
        rig.root.orientation = simd_quatf(simd_float3x3(columns: (right, up, forward)))

        var scale: Float = 1
        switch enc.state {
        case .entering:
            let p = min(1, Float(enc.age) / 0.5)
            scale = p * (1 + 0.15 * sin(p * .pi))
        case .caught:
            scale = 1 + min(1, Float(enc.age) * 4) * 0.25
        default:
            break
        }
        scale *= 1 + Float(enc.pop) * 0.15
        rig.root.scale = SIMD3(repeating: max(0.001, scale))

        let pose = enc.state == .fleeing ? CreaturePose(mouthOpen: 0.6, browUp: 1) : enc.current.pose
        rig.apply(pose, time: clock)

        // Speech bubble anchor, and keep the creature on screen.
        if let point = view.project(position + SIMD3(0, CreatureBuilder.r * 1.6, 0)) {
            game.bubblePoint = point
            let margin: CGFloat = 36
            if flipCooldown == 0, enc.state == .live, point.x < margin || point.x > view.bounds.width - margin {
                game.flipSide()
                flipCooldown = 1.5
            }
        }

        if enc.state == .caught, !snapshotTaken, enc.age > 0.12 {
            snapshotTaken = true
            view.snapshot(saveToHDR: false) { [weak self] image in
                DispatchQueue.main.async { self?.game.completeCatch(snapshot: image) }
            }
        }
    }

    /// Where the creature sits: beside the forehead, slightly behind the face plane.
    private func target(for enc: Encounter, face: simd_float4x4?, camT: simd_float4x4) -> SIMD3<Float> {
        if let face {
            let p = face * SIMD4<Float>(enc.side * 0.105, 0.085, -0.02, 1)
            return SIMD3(p.x, p.y, p.z)
        }
        let p = camT * SIMD4<Float>(0, 0, -0.4, 1)
        return SIMD3(p.x, p.y, p.z)
    }

    private static func origin(_ m: simd_float4x4) -> SIMD3<Float> {
        SIMD3(m.columns.3.x, m.columns.3.y, m.columns.3.z)
    }
}
