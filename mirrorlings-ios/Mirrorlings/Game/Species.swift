import SwiftUI

enum Rarity: String, CaseIterable {
    case common, uncommon, rare, mythic

    var label: String { rawValue.capitalized }
    var weight: Double {
        switch self { case .common: 60; case .uncommon: 26; case .rare: 11; case .mythic: 3 }
    }
    /// How many faces in a row the player has to copy.
    var steps: Int {
        switch self { case .common: 1; case .uncommon: 2; case .rare: 2; case .mythic: 3 }
    }
    /// Seconds before the creature gets bored and leaves.
    var timeLimit: Double {
        switch self { case .common: 14; case .uncommon: 18; case .rare: 20; case .mythic: 24 }
    }
    var hex: UInt32 {
        switch self { case .common: 0xC9CFDC; case .uncommon: 0x7FE0A8; case .rare: 0x86B8FF; case .mythic: 0xFF9BE0 }
    }
    var color: Color { Color(hex: hex) }
}

/// The 3D build a creature uses. See CreatureBuilder.
enum BodyKind {
    case worm, glitch, ghost, box, runner, headphones, sprout, owl, halo, twin, aura, gem
}

/// What the world has to look like for a creature to show up.
struct WorldContext {
    var daylight: Bool
    var faces: Int
    var secondsSinceCatch: Double
    var distinctCaught: Int
    var dropLive: Bool
    var now: Date
}

enum Condition {
    case daylight
    case lateNight
    case idle(seconds: Double)
    case twoFaces
    case collected(Int)
    case dropLive

    func isMet(_ c: WorldContext) -> Bool {
        switch self {
        case .daylight: return c.daylight
        case .lateNight:
            let h = Calendar.current.component(.hour, from: c.now)
            return h >= 22 || h < 4
        case .idle(let s): return c.secondsSinceCatch > s
        case .twoFaces: return c.faces >= 2
        case .collected(let n): return c.distinctCaught >= n
        case .dropLive: return c.dropLive
        }
    }

    var isDrop: Bool {
        if case .dropLive = self { return true }
        return false
    }
}

struct Species: Identifiable {
    let id: String
    let name: String
    let rarity: Rarity
    let body: BodyKind
    let primary: UInt32
    let secondary: UInt32
    let moves: [Expression]
    var firstMove: Expression? = nil
    var condition: Condition? = nil
    var needsTwo = false
    var randomPalette = false
    let lore: String
    let hint: String
}

extension Species {
    static let boxPalettes: [(UInt32, UInt32)] = [
        (0xFFD84A, 0xFFF3B8), (0x8FD1FF, 0xD9F0FF), (0xFF9BE0, 0xFFD8F3), (0xB6F27A, 0xE8FCCF), (0xC3A6FF, 0xEBE1FF),
    ]

    static let all: [Species] = [
        Species(id: "scrollwyrm", name: "Scrollwyrm", rarity: .common, body: .worm,
                primary: 0x7C6CFF, secondary: 0xC3BAFF, moves: [.smile, .jawDrop, .browsUp],
                lore: "Lives in the feed. Eats the hours you lose to it.",
                hint: "Shows up anywhere."),
        Species(id: "slopgob", name: "Slopgob", rarity: .common, body: .glitch,
                primary: 0xFF8FB1, secondary: 0xFFD6E2, moves: [.tongue, .jawDrop, .wink],
                lore: "Stitched together from a million generated images. Has slightly too many fingers.",
                hint: "Shows up anywhere."),
        Species(id: "ghostie", name: "Ghostie", rarity: .common, body: .ghost,
                primary: 0xE8ECFF, secondary: 0xC3C9EC, moves: [.blink, .kiss, .smile],
                lore: "Left you on read in 2024. Back now, acting like nothing happened.",
                hint: "Shows up anywhere."),
        Species(id: "boxling", name: "Boxling", rarity: .uncommon, body: .box,
                primary: 0xFFD84A, secondary: 0xFFF3B8, moves: [.puff, .smile, .wink, .kiss], randomPalette: true,
                lore: "A blind box that opened itself. Nobody knows what was inside, Boxling included.",
                hint: "Shows up anywhere, but not often. Comes in five colours."),
        Species(id: "pacer", name: "Pacer", rarity: .uncommon, body: .runner,
                primary: 0xFF9B54, secondary: 0xFFD5B5, moves: [.jawDrop, .puff, .browsUp],
                lore: "Joins every run club for the people. Has never finished a 5K.",
                hint: "Shows up anywhere, but not often."),
        Species(id: "lockling", name: "Lockling", rarity: .uncommon, body: .headphones,
                primary: 0x5FD3C4, secondary: 0xBFF3EC, moves: [.lockIn, .blink], firstMove: .lockIn,
                lore: "Locked in. Noise cancelling on. Do not disturb.",
                hint: "Shows up anywhere, but not often."),
        Species(id: "grasslet", name: "Grasslet", rarity: .uncommon, body: .sprout,
                primary: 0x7ED66B, secondary: 0xD2F5C4, moves: [.smile, .browsUp, .kiss], condition: .daylight,
                lore: "Only shows up for people who actually went outside.",
                hint: "Only appears in daylight. Go outside."),
        Species(id: "owlnight", name: "Owlnight", rarity: .rare, body: .owl,
                primary: 0x5263C4, secondary: 0xA6B1F0, moves: [.blink, .wink, .jawDrop], condition: .lateNight,
                lore: "Way past its screen-time limit. Doesn't care.",
                hint: "Only appears between 10pm and 4am."),
        Species(id: "detoxie", name: "Detoxie", rarity: .rare, body: .halo,
                primary: 0x9FE3C6, secondary: 0xE6F8F0, moves: [.blink, .smile, .puff], condition: .idle(seconds: 45),
                lore: "Shows up once you stop chasing things. Smells like a phone left in another room.",
                hint: "Appears after 45 seconds without a catch."),
        Species(id: "duetto", name: "Duetto", rarity: .rare, body: .twin,
                primary: 0xFF6F91, secondary: 0xFFC7D5, moves: [.smile, .jawDrop, .tongue], condition: .twoFaces, needsTwo: true,
                lore: "Can't be caught alone. Bring someone real.",
                hint: "Needs two faces in the mirror, both copying it."),
        Species(id: "aurafarmer", name: "Aurafarmer", rarity: .mythic, body: .aura,
                primary: 0xF4C542, secondary: 0xFFF1BF, moves: [.lockIn, .smile, .wink, .browsUp], condition: .collected(5),
                lore: "Never tries. Never has to.",
                hint: "Appears once you have five different Mirrorlings."),
        Species(id: "flashdrop", name: "Flashdrop", rarity: .mythic, body: .gem,
                primary: 0xFFE14D, secondary: 0xFFFFFF, moves: [.jawDrop, .smile, .tongue, .puff], condition: .dropLive,
                lore: "Exists for two minutes a day, at the same moment for everyone. Then it's gone.",
                hint: "Only during The Drop, two minutes a day. Turn on Drop alerts."),
    ]
}
