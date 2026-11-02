# Mirrorlings (iOS)

Collectible creatures that live in your reflection. The app opens on the front camera; a Mirrorling peeks over your shoulder and pulls a face, and you catch it by copying that face and holding it. The 2016 creature-hunting craze, rethought for 2026: you're in the frame, you go outside for the rare ones, and you bring friends in person.

## Run it on your iPhone

1. Open `Mirrorlings.xcodeproj` in Xcode 16 or newer.
2. Select the **Mirrorlings** target → *Signing & Capabilities* → pick your team. Change the bundle id if `work.theflux.mirrorlings` is taken on your account.
3. Plug in an iPhone with Face ID (TrueDepth camera, iPhone X or newer) and press Run. The simulator can't do face tracking.

In Debug builds, triple-tap the face-count chip to start a test Drop.

## How it plays

| Mechanic | How it works |
|---|---|
| Catching | The creature makes a face; copy and hold it. Commons need 1 face, uncommons and rares 2, mythics 3. It leaves if you take too long. |
| Faces read | Smile, blink, wink, eyebrows up, jaw drop, kissy face, frown ("lock in"), puffed cheeks, tongue out. All come from ARKit's TrueDepth blendshapes. |
| Proof of human | Play starts with a blink. TrueDepth reads depth, so a photo or a screen can't stand in for a face. |
| Touch grass | Grasslet only appears when ARKit's light estimate says you're in daylight. |
| Bring someone real | Duetto needs two tracked faces, both copying it. |
| The Drop | Two minutes a day at the same local time for everyone (picked from the date, no server). Optional notification. Flashdrop only exists then. |
| Blind boxes | Boxling spawns in one of five colourways. |
| Shelf | Every catch saves a 3:4 selfie with the creature, stamped and ready to share. |

## Code map

| Path | What |
|---|---|
| `Mirrorlings/Game/GameModel.swift` | State machine: liveness → roaming → encounter → catch card |
| `Mirrorlings/Game/Expressions.swift` | Blendshape thresholds per face, and the pose each creature shows |
| `Mirrorlings/Game/Species.swift` | The 12 creatures, rarities and spawn conditions |
| `Mirrorlings/Game/DropScheduler.swift` | Daily Drop time and notifications |
| `Mirrorlings/Game/ShelfStore.swift`, `PhotoCard.swift` | Collection on disk; catch photo |
| `Mirrorlings/AR/MirrorView.swift` | ARKit face tracking, creature placement next to your head, snapshot |
| `Mirrorlings/AR/CreatureBuilder.swift` | Creatures built from RealityKit primitives with animated faces |
| `Mirrorlings/UI/` | SwiftUI intro, HUD, bubble, catch card, shelf |

## Prototype limits

- Creatures are built from primitive shapes. Real art would be USDZ models swapped in at `CreatureBuilder.make`.
- Expression thresholds and the daylight cut-off are first guesses and need tuning on device.
- No sound yet; catches and steps use haptics.
- `.github/workflows/mirrorlings-ios.yml` compiles the app on a macOS runner (unsigned) on every push.
