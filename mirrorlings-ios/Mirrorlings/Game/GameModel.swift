import ARKit
import Observation
import UIKit
import simd

struct TrackedFace {
    let shapes: Blendshapes
    let transform: simd_float4x4
}

struct Encounter: Identifiable {
    enum State { case entering, live, fleeing, caught }

    let id = UUID()
    let species: Species
    let sequence: [Expression]
    var step = 0
    var progress: Double = 0
    var timeLeft: Double
    let timeLimit: Double
    var state: State = .entering
    var age: Double = 0
    var pop: Double = 0
    /// Which side of the player's head it sits on, in face space (+1 or -1).
    var side: Float
    let primary: UInt32
    let secondary: UInt32

    var current: Expression { sequence[min(step, sequence.count - 1)] }
}

struct CatchResult: Identifiable {
    let id = UUID()
    let species: Species
    let photo: UIImage
    let isNew: Bool
    let count: Int
}

/// The whole game loop. MirrorCoordinator calls `tick` once per rendered frame
/// on the main thread; SwiftUI reads the published state.
@Observable
final class GameModel {
    enum Phase { case intro, liveness, roaming, catching, card }

    var phase: Phase = .intro
    var faceCount = 0
    var daylight = false
    var status: String?
    var toast: String?
    var toastID = 0
    var encounter: Encounter?
    var bubblePoint: CGPoint?
    var lastCatch: CatchResult?
    var showShelf = false
    var cameraProblem: String?
    var dropSecondsLeft: Int?
    var stepPulse = 0
    var catchPulse = 0

    let shelf = ShelfStore()
    let drop = DropScheduler()

    @ObservationIgnored private var faces: [TrackedFace] = []
    @ObservationIgnored private var spawnIn = 1.5
    @ObservationIgnored private var sinceCatch = 0.0
    @ObservationIgnored private var secondTimer = 0.0

    // MARK: Lifecycle

    func start() {
        guard ARFaceTrackingConfiguration.isSupported else {
            cameraProblem = "Mirrorlings needs a TrueDepth front camera (iPhone X or newer) to read your face."
            return
        }
        cameraProblem = nil
        phase = .liveness
    }

    func cameraFailed(_ message: String) {
        cameraProblem = message
        encounter = nil
        phase = .intro
    }

    func dismissCard() {
        encounter = nil
        bubblePoint = nil
        phase = .roaming
        spawnIn = 2
        sinceCatch = 0
    }

    func flipSide() {
        encounter?.side *= -1
    }

    #if DEBUG
    func debugStartDrop() {
        drop.debugStart = .now
        showToast("Debug: The Drop started")
    }
    #endif

    // MARK: Frame loop

    func tick(dt: Double, faces newFaces: [TrackedFace], ambient: Float?) {
        faces = newFaces
        if faceCount != newFaces.count { faceCount = newFaces.count }

        if let a = ambient {
            // ARKit reports ~1000 lumens for a normal room. Hysteresis stops flicker.
            let lit = daylight ? a > 1300 : a > 1700
            if lit != daylight { daylight = lit }
        }

        secondTimer -= dt
        if secondTimer <= 0 {
            secondTimer = 0.5
            let left = drop.secondsLeft()
            if left != dropSecondsLeft { dropSecondsLeft = left }
        }

        switch phase {
        case .liveness:
            guard let face = newFaces.first else { return setStatus("Show your face to the mirror") }
            setStatus("Blink at the mirror. Mirrorlings only trust real faces.")
            if min(face.shapes[.eyeBlinkLeft], face.shapes[.eyeBlinkRight]) > 0.5 {
                phase = .roaming
                spawnIn = 1.2
                stepPulse += 1
                showToast("Real human confirmed")
            }
        case .roaming:
            sinceCatch += dt
            if encounter == nil {
                setStatus(newFaces.isEmpty ? "Find your face in the mirror" : "Looking for Mirrorlings…")
                if !newFaces.isEmpty {
                    spawnIn -= dt
                    if spawnIn <= 0 { spawn() }
                }
            } else {
                updateEncounter(dt)
            }
        case .catching:
            encounter?.age += dt
        case .intro, .card:
            break
        }
    }

    private func updateEncounter(_ dt: Double) {
        guard var e = encounter else { return }
        e.age += dt
        e.pop = max(0, e.pop - dt * 3)

        switch e.state {
        case .entering:
            if e.age > 0.5 { e.state = .live }
        case .live:
            e.timeLeft -= dt
            let move = e.current
            let ok: Bool
            if e.species.needsTwo {
                ok = faces.count >= 2 && faces.prefix(2).allSatisfy { move.isHeld($0.shapes) }
            } else {
                ok = faces.first.map { move.isHeld($0.shapes) } ?? false
            }
            e.progress = ok ? e.progress + dt / move.hold : max(0, e.progress - dt * 1.2)

            if e.species.needsTwo && faces.count < 2 {
                setStatus("\(e.species.name) needs two faces. Get a friend in the frame.")
            } else if faces.isEmpty {
                setStatus("Come back! Find your face in the mirror")
            } else {
                setStatus(nil)
            }

            if e.progress >= 1 {
                e.step += 1
                e.progress = 0
                e.pop = 1
                stepPulse += 1
                if e.step >= e.sequence.count {
                    e.state = .caught
                    e.age = 0
                    encounter = e
                    phase = .catching
                    catchPulse += 1
                    setStatus(nil)
                    return
                }
                e.timeLeft = min(e.timeLimit, e.timeLeft + 4)
            } else if e.timeLeft <= 0 {
                e.state = .fleeing
                e.age = 0
                showToast("\(e.species.name) got bored and left")
            }
        case .fleeing:
            if e.age > 0.9 {
                encounter = nil
                bubblePoint = nil
                spawnIn = 2.5
                return
            }
        case .caught:
            break
        }
        encounter = e
    }

    private func spawn() {
        let ctx = WorldContext(daylight: daylight, faces: faces.count, secondsSinceCatch: sinceCatch,
                               distinctCaught: shelf.count, dropLive: dropSecondsLeft != nil, now: .now)
        let pool = Species.all.filter { $0.condition?.isMet(ctx) ?? true }
        guard !pool.isEmpty else { return }
        let weights = pool.map { s -> Double in
            var w = s.rarity.weight
            if let c = s.condition { w *= c.isDrop ? 40 : 3 }
            if !shelf.has(s.id) { w *= 1.5 }
            return w
        }
        var roll = Double.random(in: 0..<weights.reduce(0, +))
        var chosen = pool[0]
        for (s, w) in zip(pool, weights) {
            roll -= w
            if roll < 0 { chosen = s; break }
        }

        var seq: [Expression] = []
        for i in 0..<chosen.rarity.steps {
            var move = chosen.moves.randomElement() ?? .smile
            while chosen.moves.count > 1, i > 0, move == seq[i - 1] {
                move = chosen.moves.randomElement() ?? .smile
            }
            seq.append(move)
        }
        if let first = chosen.firstMove { seq[0] = first }

        let palette = chosen.randomPalette
            ? (Species.boxPalettes.randomElement() ?? (chosen.primary, chosen.secondary))
            : (chosen.primary, chosen.secondary)
        encounter = Encounter(species: chosen, sequence: seq, timeLeft: chosen.rarity.timeLimit,
                              timeLimit: chosen.rarity.timeLimit, side: Bool.random() ? 1 : -1,
                              primary: palette.0, secondary: palette.1)
        showToast("\(chosen.name) is peeking over your shoulder")
    }

    /// Called by the AR view once it has photographed the catch.
    func completeCatch(snapshot: UIImage?) {
        guard phase == .catching, let e = encounter else { return }
        let photo = PhotoCard.make(from: snapshot, species: e.species)
        let saved = shelf.record(e.species, photo: photo)
        lastCatch = CatchResult(species: e.species, photo: photo, isNew: saved.isNew, count: saved.count)
        sinceCatch = 0
        phase = .card
    }

    // MARK: Messages

    private func setStatus(_ text: String?) {
        if status != text { status = text }
    }

    func showToast(_ text: String) {
        toast = text
        toastID += 1
    }
}
