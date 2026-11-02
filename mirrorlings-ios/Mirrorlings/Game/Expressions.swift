import ARKit

/// ARKit's 52 blendshape readings for one face, as plain Floats.
struct Blendshapes {
    private var values: [ARFaceAnchor.BlendShapeLocation: Float] = [:]

    init(_ raw: [ARFaceAnchor.BlendShapeLocation: NSNumber]) {
        for (key, value) in raw { values[key] = value.floatValue }
    }

    subscript(_ key: ARFaceAnchor.BlendShapeLocation) -> Float { values[key] ?? 0 }
}

/// How a creature's face is posed. Every value runs 0...1.
struct CreaturePose {
    var eyeL: Float = 0
    var eyeR: Float = 0
    var mouthOpen: Float = 0
    var smile: Float = 0
    var browUp: Float = 0
    var browDown: Float = 0
    var pucker: Float = 0
    var puff: Float = 0
    var tongue: Float = 0
}

/// A face the player has to copy. Each one reads ARKit blendshapes and
/// says whether the player is holding it.
enum Expression: String, CaseIterable, Codable {
    case smile, blink, wink, browsUp, jawDrop, kiss, lockIn, puff, tongue

    var prompt: String {
        switch self {
        case .smile: "Smile big"
        case .blink: "Close both eyes"
        case .wink: "Wink"
        case .browsUp: "Eyebrows up"
        case .jawDrop: "Jaw drop"
        case .kiss: "Kissy face"
        case .lockIn: "Lock in (frown)"
        case .puff: "Puff your cheeks"
        case .tongue: "Tongue out"
        }
    }

    /// Seconds the player has to hold the face.
    var hold: Double {
        switch self {
        case .blink: 0.45
        case .wink: 0.5
        case .lockIn: 0.9
        default: 0.8
        }
    }

    /// 1.0 or more means the player is making this face.
    func strength(_ b: Blendshapes) -> Float {
        switch self {
        case .smile:
            return (b[.mouthSmileLeft] + b[.mouthSmileRight]) / 2 / 0.5
        case .blink:
            return min(b[.eyeBlinkLeft], b[.eyeBlinkRight]) / 0.6
        case .wink:
            let l = b[.eyeBlinkLeft], r = b[.eyeBlinkRight]
            return max(l, r) > 0.6 ? abs(l - r) / 0.4 : 0
        case .browsUp:
            return b[.browInnerUp] / 0.55
        case .jawDrop:
            return b[.jawOpen] / 0.45
        case .kiss:
            return b[.mouthPucker] / 0.6
        case .lockIn:
            return (b[.browDownLeft] + b[.browDownRight]) / 2 / 0.4
        case .puff:
            return b[.cheekPuff] / 0.45
        case .tongue:
            return b[.tongueOut] / 0.4
        }
    }

    func isHeld(_ b: Blendshapes) -> Bool { strength(b) >= 1 }

    /// The creature demonstrates the face it wants.
    var pose: CreaturePose {
        switch self {
        case .smile: CreaturePose(smile: 1)
        case .blink: CreaturePose(eyeL: 1, eyeR: 1)
        case .wink: CreaturePose(eyeR: 1, smile: 0.6)
        case .browsUp: CreaturePose(browUp: 1)
        case .jawDrop: CreaturePose(mouthOpen: 1, browUp: 0.5)
        case .kiss: CreaturePose(pucker: 1)
        case .lockIn: CreaturePose(browDown: 1)
        case .puff: CreaturePose(puff: 1)
        case .tongue: CreaturePose(mouthOpen: 0.4, tongue: 1)
        }
    }
}
