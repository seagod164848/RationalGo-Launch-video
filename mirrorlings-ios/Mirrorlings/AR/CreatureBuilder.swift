import RealityKit
import UIKit

/// A built creature: its entity tree plus handles on the parts that animate.
/// Creatures are built facing +Z; MirrorCoordinator turns +Z toward the camera.
final class CreatureRig {
    struct FaceParts {
        let eyeL: ModelEntity
        let eyeR: ModelEntity
        let mouth: ModelEntity
        let browL: ModelEntity
        let browR: ModelEntity
        let tongue: ModelEntity
        let cheekL: ModelEntity
        let cheekR: ModelEntity
        let browY: Float
        let mouthY: Float
        let r: Float
    }

    let root = Entity()
    let bob = Entity()
    var faces: [FaceParts] = []
    var puffTargets: [(Entity, SIMD3<Float>)] = []
    var animators: [(Float) -> Void] = []
    let ink = UnlitMaterial(color: UIColor(hex: 0x1B1426))
    let pink = UnlitMaterial(color: UIColor(hex: 0xFF5C8A))

    init() { root.addChild(bob) }

    func apply(_ p: CreaturePose, time t: Float) {
        bob.position.y = sin(t * 3) * 0.003
        let idleBlink: Float = fmodf(t, 3.7) < 0.13 ? 1 : 0

        for f in faces {
            let l = max(p.eyeL, idleBlink)
            let r = max(p.eyeR, p.eyeL > 0 ? 0 : idleBlink)
            f.eyeL.scale = SIMD3(1, l > 0.5 ? 0.15 : 1, 1)
            f.eyeR.scale = SIMD3(1, r > 0.5 ? 0.15 : 1, 1)

            let browsOn = p.browUp > 0 || p.browDown > 0
            f.browL.isEnabled = browsOn
            f.browR.isEnabled = browsOn
            let by = f.browY + p.browUp * f.r * 0.16
            f.browL.position.y = by
            f.browR.position.y = by
            f.browL.orientation = simd_quatf(angle: -p.browDown * 0.5, axis: SIMD3(0, 0, 1))
            f.browR.orientation = simd_quatf(angle: p.browDown * 0.5, axis: SIMD3(0, 0, 1))

            var mouthMaterial: any Material = ink
            var mouthScale = SIMD3<Float>(0.7, 0.25, 0.5)
            var mouthY = f.mouthY
            if p.pucker > 0 {
                mouthMaterial = pink
                mouthScale = SIMD3(0.55, 0.6, 0.7)
            } else if p.mouthOpen > 0 {
                mouthScale = SIMD3(0.85, 0.5 + 1.1 * p.mouthOpen, 0.6)
                mouthY -= f.r * 0.04
            } else if p.smile > 0 {
                mouthScale = SIMD3(1.6, 0.3 + 0.4 * p.smile, 0.5)
            } else if p.puff > 0 {
                mouthScale = SIMD3(0.45, 0.2, 0.5)
            } else if p.browDown > 0 {
                mouthScale = SIMD3(0.9, 0.15, 0.5)
            }
            f.mouth.model?.materials = [mouthMaterial]
            f.mouth.scale = mouthScale
            f.mouth.position.y = mouthY
            f.tongue.isEnabled = p.tongue > 0

            let cheek: Float = p.puff > 0 ? 1.7 : 1
            f.cheekL.scale = SIMD3(cheek, cheek * 0.6, cheek * 0.5)
            f.cheekR.scale = SIMD3(cheek, cheek * 0.6, cheek * 0.5)
        }

        for (body, base) in puffTargets {
            body.scale = base * SIMD3(1 + p.puff * 0.12, 1, 1 + p.puff * 0.05)
        }
        for animate in animators { animate(t) }
    }
}

enum CreatureBuilder {
    /// Body radius in metres. A face is roughly 0.15 m wide, so creatures read as shoulder pets.
    static let r: Float = 0.045

    static func make(_ species: Species, primary: UInt32, secondary: UInt32) -> CreatureRig {
        let r = Self.r
        let rig = CreatureRig()
        let skin = vinyl(UIColor(hex: primary))
        let trim = vinyl(UIColor(hex: secondary))
        let dark = vinyl(UIColor(hex: 0x1B1426))
        let bob = rig.bob

        switch species.body {
        case .twin:
            for d: Float in [-1, 1] {
                let holder = Entity()
                holder.position = SIMD3(d * r * 0.62, 0, 0)
                holder.scale = SIMD3(repeating: 0.68)
                bob.addChild(holder)
                sphereBody(d < 0 ? skin : trim, in: holder, rig: rig)
                belly(d < 0 ? trim : skin, in: holder)
                addFace(to: holder, rig: rig)
                rig.animators.append { t in holder.position.y = sin(t * 4 + d) * r * 0.08 }
            }
            return rig

        case .box:
            let body = part(.generateBox(size: r * 1.7, cornerRadius: r * 0.3), skin, at: .zero, in: bob)
            rig.puffTargets.append((body, .one))
            part(.generateBox(width: r * 1.74, height: r * 0.22, depth: r * 1.74, cornerRadius: r * 0.05), trim,
                 at: SIMD3(0, -r * 0.5, 0), in: bob)
            for d: Float in [-1, 1] {
                let loop = part(.generateSphere(radius: r * 0.26), trim, at: SIMD3(d * r * 0.25, r * 0.95, 0),
                                scale: SIMD3(1.3, 0.7, 0.7), in: bob)
                loop.orientation = simd_quatf(angle: -d * 0.4, axis: SIMD3(0, 0, 1))
            }
            addFace(to: bob, rig: rig, dz: r * 0.12)
            rig.animators.append { t in bob.orientation = simd_quatf(angle: sin(t * 2) * 0.06, axis: SIMD3(0, 0, 1)) }
            return rig

        case .gem:
            let gem = part(.generateBox(size: r * 1.45, cornerRadius: r * 0.12), skin, at: .zero, in: bob)
            gem.orientation = simd_quatf(angle: .pi / 4, axis: SIMD3(0, 0, 1))
            rig.puffTargets.append((gem, .one))
            addFace(to: bob, rig: rig, dz: -r * 0.02)
            let orbit = Entity()
            bob.addChild(orbit)
            let spark = glow(.white, opacity: 0.95)
            for i in 0..<4 {
                let a = Float(i) * .pi / 2
                part(.generateSphere(radius: r * 0.08), spark, at: SIMD3(cos(a) * r * 1.25, sin(a) * r * 0.3, sin(a) * r * 1.25), in: orbit)
            }
            rig.animators.append { t in orbit.orientation = simd_quatf(angle: t * 2.5, axis: SIMD3(0, 1, 0)) }
            return rig

        default:
            sphereBody(skin, in: bob, rig: rig)
            if species.body != .glitch { belly(trim, in: bob) }
            addFace(to: bob, rig: rig)
        }

        switch species.body {
        case .worm:
            for i in 1...4 {
                let fi = Float(i)
                let seg = part(.generateSphere(radius: r * (0.5 - fi * 0.07)), i % 2 == 0 ? skin : trim,
                               at: SIMD3(-(r * 0.55 + fi * r * 0.42), -r * 0.3 - fi * r * 0.08, -r * 0.25 - fi * r * 0.1), in: bob)
                let baseY = seg.position.y
                rig.animators.append { t in seg.position.y = baseY + sin(t * 4 - fi) * r * 0.1 }
            }

        case .glitch:
            let cyan = part(.generateSphere(radius: r), glow(UIColor(hex: 0x3DF2FF), opacity: 0.4),
                            at: SIMD3(-r * 0.08, 0, -r * 0.05), scale: SIMD3(1, 0.92, 0.88), in: bob)
            let magenta = part(.generateSphere(radius: r), glow(UIColor(hex: 0xFF3DF2), opacity: 0.4),
                               at: SIMD3(r * 0.08, 0, -r * 0.05), scale: SIMD3(1, 0.92, 0.88), in: bob)
            for i in 0..<7 {
                let a = Float.pi * (1.15 + Float(i) * 0.1)
                let nub = part(.generateSphere(radius: r * 0.12), skin, at: SIMD3(cos(a) * r * 0.95, sin(a) * r * 0.86, r * 0.1),
                               scale: SIMD3(0.8, 1.3, 0.8), in: bob)
                nub.orientation = simd_quatf(angle: a + .pi / 2, axis: SIMD3(0, 0, 1))
            }
            rig.animators.append { t in
                let jump: Float = Int(t * 8) % 13 == 0 ? r * 0.14 : 0
                cyan.position.x = -r * 0.08 - jump
                magenta.position.x = r * 0.08 + jump
            }

        case .ghost:
            for i in 0..<5 {
                let fi = Float(i)
                let puff = part(.generateSphere(radius: r * 0.3), skin, at: SIMD3(-r * 0.6 + fi * r * 0.3, -r * 0.78, 0), in: bob)
                rig.animators.append { t in puff.position.y = -r * 0.78 + sin(t * 5 + fi * 1.6) * r * 0.06 }
            }

        case .runner:
            part(.generateCylinder(height: r * 0.18, radius: r * 0.97), vinyl(UIColor(hex: 0xFF4F6D)), at: SIMD3(0, r * 0.42, 0), in: bob)
            part(.generateCylinder(height: r * 0.04, radius: r * 0.985), vinyl(.white), at: SIMD3(0, r * 0.42, 0), in: bob)
            let white = vinyl(.white)
            for d: Float in [-1, 1] {
                let shoe = part(.generateSphere(radius: r * 0.2), white, at: SIMD3(d * r * 0.32, -r * 0.9, r * 0.1),
                                scale: SIMD3(1.2, 0.6, 1.6), in: bob)
                rig.animators.append { t in shoe.position.y = -r * 0.9 + max(0, sin(t * 10) * d) * r * 0.15 }
            }

        case .headphones:
            part(.generateBox(width: r * 1.3, height: r * 0.14, depth: r * 0.22, cornerRadius: r * 0.05), dark, at: SIMD3(0, r * 1.0, 0), in: bob)
            for d: Float in [-1, 1] {
                let arm = part(.generateBox(width: r * 0.14, height: r * 0.55, depth: r * 0.22, cornerRadius: r * 0.05), dark,
                               at: SIMD3(d * r * 0.78, r * 0.72, 0), in: bob)
                arm.orientation = simd_quatf(angle: -d * 0.35, axis: SIMD3(0, 0, 1))
                let cup = part(.generateCylinder(height: r * 0.24, radius: r * 0.32), dark, at: SIMD3(d * r * 0.95, r * 0.1, 0), in: bob)
                cup.orientation = simd_quatf(angle: .pi / 2, axis: SIMD3(0, 0, 1))
                let pad = part(.generateCylinder(height: r * 0.26, radius: r * 0.2), trim, at: SIMD3(d * r * 0.97, r * 0.1, 0), in: bob)
                pad.orientation = cup.orientation
            }

        case .sprout:
            part(.generateCylinder(height: r * 0.5, radius: r * 0.05), vinyl(UIColor(hex: 0x3F8F35)), at: SIMD3(0, r * 1.05, 0), in: bob)
            let leaf = vinyl(UIColor(hex: 0x4FB543))
            for d: Float in [-1, 1] {
                let l = part(.generateSphere(radius: r * 0.3), leaf, at: SIMD3(d * r * 0.3, r * 1.32, 0), scale: SIMD3(1.4, 0.35, 0.7), in: bob)
                rig.animators.append { t in l.orientation = simd_quatf(angle: d * (0.5 + sin(t * 3) * 0.12), axis: SIMD3(0, 0, 1)) }
            }

        case .owl:
            for d: Float in [-1, 1] {
                let tuft = part(.generateCone(height: r * 0.5, radius: r * 0.2), skin, at: SIMD3(d * r * 0.5, r * 0.95, 0), in: bob)
                tuft.orientation = simd_quatf(angle: -d * 0.3, axis: SIMD3(0, 0, 1))
            }

        case .halo:
            let ring = Entity()
            ring.position = SIMD3(0, r * 1.2, 0)
            bob.addChild(ring)
            let light = glow(UIColor(hex: 0xE6F8F0), opacity: 0.8)
            for i in 0..<16 {
                let a = Float(i) / 16 * 2 * .pi
                part(.generateSphere(radius: r * 0.07), light, at: SIMD3(cos(a) * r * 0.5, 0, sin(a) * r * 0.5), in: ring)
            }
            rig.animators.append { t in
                ring.orientation = simd_quatf(angle: t * 0.8, axis: SIMD3(0, 1, 0))
                ring.position.y = r * 1.2 + sin(t * 2) * r * 0.05
            }

        case .aura:
            let aura = part(.generateSphere(radius: r * 1.7), glow(UIColor(hex: 0xFFD75A), opacity: 0.2), at: .zero, in: bob)
            rig.animators.append { t in aura.scale = SIMD3(repeating: 1 + sin(t * 2) * 0.06) }
            for d: Float in [-1, 1] {
                part(.generateBox(width: r * 0.42, height: r * 0.2, depth: r * 0.08, cornerRadius: r * 0.04), dark,
                     at: SIMD3(d * r * 0.26, r * 0.62, r * 0.7), in: bob)
            }
            part(.generateBox(width: r * 0.14, height: r * 0.04, depth: r * 0.06, cornerRadius: r * 0.01), dark,
                 at: SIMD3(0, r * 0.64, r * 0.72), in: bob)

        default:
            break
        }
        return rig
    }

    // MARK: Parts

    static func vinyl(_ color: UIColor) -> PhysicallyBasedMaterial {
        var m = PhysicallyBasedMaterial()
        m.baseColor = .init(tint: color)
        m.roughness = .init(floatLiteral: 0.38)
        m.metallic = .init(floatLiteral: 0)
        m.clearcoat = .init(floatLiteral: 0.7)
        m.clearcoatRoughness = .init(floatLiteral: 0.15)
        return m
    }

    static func glow(_ color: UIColor, opacity: Float) -> UnlitMaterial {
        var m = UnlitMaterial(color: color)
        m.blending = .transparent(opacity: .init(floatLiteral: opacity))
        return m
    }

    @discardableResult
    static func part(_ mesh: MeshResource, _ material: any Material, at position: SIMD3<Float>,
                     scale: SIMD3<Float> = .one, in parent: Entity) -> ModelEntity {
        let e = ModelEntity(mesh: mesh, materials: [material])
        e.position = position
        e.scale = scale
        parent.addChild(e)
        return e
    }

    @discardableResult
    static func sphereBody(_ material: any Material, in parent: Entity, rig: CreatureRig) -> ModelEntity {
        let base = SIMD3<Float>(1, 0.92, 0.88)
        let body = part(.generateSphere(radius: r), material, at: .zero, scale: base, in: parent)
        rig.puffTargets.append((body, base))
        return body
    }

    static func belly(_ material: any Material, in parent: Entity) {
        part(.generateSphere(radius: r * 0.5), material, at: SIMD3(0, -r * 0.55, r * 0.5), scale: SIMD3(1, 0.6, 0.45), in: parent)
    }

    static func addFace(to parent: Entity, rig: CreatureRig, dz: Float = 0) {
        let white = UnlitMaterial(color: .white)
        let blush = glow(UIColor(hex: 0xFF6E96), opacity: 0.55)

        let eyeMesh = MeshResource.generateSphere(radius: r * 0.15)
        let eyeL = part(eyeMesh, rig.ink, at: SIMD3(-r * 0.36, r * 0.14, r * 0.78 + dz), in: parent)
        let eyeR = part(eyeMesh, rig.ink, at: SIMD3(r * 0.36, r * 0.14, r * 0.78 + dz), in: parent)
        for eye in [eyeL, eyeR] {
            part(.generateSphere(radius: r * 0.05), white, at: SIMD3(r * 0.05, r * 0.06, r * 0.12), in: eye)
        }

        let browY = r * 0.42
        let browMesh = MeshResource.generateBox(width: r * 0.34, height: r * 0.07, depth: r * 0.06, cornerRadius: r * 0.025)
        let browL = part(browMesh, rig.ink, at: SIMD3(-r * 0.36, browY, r * 0.74 + dz), in: parent)
        let browR = part(browMesh, rig.ink, at: SIMD3(r * 0.36, browY, r * 0.74 + dz), in: parent)

        let mouthY = -r * 0.24
        let mouth = part(.generateSphere(radius: r * 0.14), rig.ink, at: SIMD3(0, mouthY, r * 0.82 + dz), in: parent)
        let tongue = part(.generateSphere(radius: r * 0.1), rig.pink, at: SIMD3(0, mouthY - r * 0.16, r * 0.86 + dz),
                          scale: SIMD3(0.9, 1.2, 0.5), in: parent)

        let cheekMesh = MeshResource.generateSphere(radius: r * 0.11)
        let cheekL = part(cheekMesh, blush, at: SIMD3(-r * 0.56, -r * 0.1, r * 0.68 + dz), scale: SIMD3(1, 0.6, 0.5), in: parent)
        let cheekR = part(cheekMesh, blush, at: SIMD3(r * 0.56, -r * 0.1, r * 0.68 + dz), scale: SIMD3(1, 0.6, 0.5), in: parent)

        rig.faces.append(CreatureRig.FaceParts(eyeL: eyeL, eyeR: eyeR, mouth: mouth, browL: browL, browR: browR,
                                               tongue: tongue, cheekL: cheekL, cheekR: cheekR,
                                               browY: browY, mouthY: mouthY, r: r))
    }
}
