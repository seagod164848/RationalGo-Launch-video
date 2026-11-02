import SwiftUI

struct HUDView: View {
    @Environment(GameModel.self) private var game

    var body: some View {
        VStack(spacing: 12) {
            HStack(alignment: .top) {
                Button { game.showShelf = true } label: {
                    HStack(spacing: 8) {
                        Text("Shelf").font(.label(15))
                        Text("\(game.shelf.count)/\(Species.all.count)")
                            .font(.mono(12))
                            .foregroundStyle(Color.chrome)
                            .padding(.horizontal, 7)
                            .padding(.vertical, 4)
                            .background(Color.paperInk, in: Capsule())
                    }
                    .foregroundStyle(Color.paperInk)
                    .padding(.leading, 14)
                    .padding(.trailing, 8)
                    .padding(.vertical, 8)
                    .background(Color.chrome, in: Capsule())
                    .shadow(color: .black.opacity(0.25), radius: 0, x: 0, y: 3)
                }

                Spacer()

                VStack(alignment: .trailing, spacing: 6) {
                    if let left = game.dropSecondsLeft {
                        Chip(text: "The Drop \(left / 60):\(String(format: "%02d", left % 60))", lit: true)
                    }
                    HStack(spacing: 6) {
                        Chip(text: game.daylight ? "Daylight" : "Indoor light", lit: game.daylight)
                        Chip(text: game.faceCount == 1 ? "1 face" : "\(game.faceCount) faces")
                            #if DEBUG
                            .onTapGesture(count: 3) { game.debugStartDrop() }
                            #endif
                    }
                }
            }

            if let status = game.status {
                Text(status)
                    .font(.label(15, weight: .semibold))
                    .foregroundStyle(Color.chrome)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                    .frame(maxWidth: 360)
                    .transition(.opacity)
            }

            Spacer()

            if let toast = game.toast {
                Text(toast)
                    .font(.label(16))
                    .foregroundStyle(Color.stickerInk)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 11)
                    .background(Color.sticker, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                    .id(game.toastID)
            }
        }
        .padding(.horizontal, 14)
        .padding(.top, 8)
        .padding(.bottom, 28)
        .animation(.spring(duration: 0.35), value: game.toastID)
        .animation(.easeInOut(duration: 0.2), value: game.status)
        .task(id: game.toastID) {
            guard game.toast != nil else { return }
            try? await Task.sleep(for: .seconds(2.4))
            if !Task.isCancelled { game.toast = nil }
        }
    }
}

/// The "copy this face" bubble that floats above the creature.
struct EncounterBubble: View {
    @Environment(GameModel.self) private var game

    var body: some View {
        GeometryReader { geo in
            if game.phase == .roaming, let e = game.encounter, e.state == .live || e.state == .entering,
               let p = game.bubblePoint {
                BubbleCard(encounter: e)
                    .fixedSize()
                    .position(x: min(max(p.x, 110), geo.size.width - 110), y: max(p.y - 52, 150))
                    .allowsHitTesting(false)
            }
        }
    }
}

struct BubbleCard: View {
    let encounter: Encounter
    private let width: CGFloat = 156

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            Text((encounter.species.needsTwo ? "Both: " : "") + encounter.current.prompt)
                .font(.label(17))

            ZStack(alignment: .leading) {
                Capsule().fill(Color.paperInk.opacity(0.12))
                Capsule().fill(Color.sticker).frame(width: width * min(1, encounter.progress))
            }
            .frame(width: width, height: 8)

            HStack(spacing: 5) {
                ForEach(0..<encounter.sequence.count, id: \.self) { i in
                    Circle()
                        .fill(i < encounter.step ? Color(hex: 0x2FBF71) : i == encounter.step ? Color.paperInk : Color.paperInk.opacity(0.2))
                        .frame(width: 7, height: 7)
                }
                Spacer(minLength: 8)
                Text("\(Int(max(0, encounter.timeLeft).rounded(.up)))s")
                    .font(.mono(11))
                    .foregroundStyle(encounter.timeLeft < 5 ? Color.alert : Color.paperInk.opacity(0.6))
            }
            .frame(width: width)
        }
        .foregroundStyle(Color.paperInk)
        .padding(12)
        .background(Color.chrome, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        .shadow(color: .black.opacity(0.25), radius: 8, y: 4)
    }
}
