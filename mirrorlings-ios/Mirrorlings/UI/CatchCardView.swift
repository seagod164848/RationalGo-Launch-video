import SwiftUI

/// The polaroid you get for a catch: your selfie with the creature in it.
struct CatchCardView: View {
    @Environment(GameModel.self) private var game
    let result: CatchResult

    var body: some View {
        ZStack {
            Color.black.opacity(0.72).ignoresSafeArea()

            VStack(spacing: 18) {
                VStack(alignment: .leading, spacing: 8) {
                    Color.clear
                        .aspectRatio(3 / 4, contentMode: .fit)
                        .overlay(Image(uiImage: result.photo).resizable().scaledToFill())
                        .clipShape(RoundedRectangle(cornerRadius: 2))

                    HStack(alignment: .firstTextBaseline) {
                        Text(result.species.name).font(.display(28))
                        Spacer()
                        RarityTag(rarity: result.species.rarity)
                    }
                    .padding(.top, 4)

                    Text(result.isNew ? "NEW ON YOUR SHELF" : "CAUGHT \(result.count) TIMES")
                        .font(.mono(11)).tracking(0.6)
                        .foregroundStyle(Color(hex: 0xB03A6A))

                    Text(result.species.lore)
                        .font(.system(size: 15))
                        .foregroundStyle(Color.paperDim)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .foregroundStyle(Color.paperInk)
                .padding(12)
                .padding(.bottom, 6)
                .background(Color.paper, in: RoundedRectangle(cornerRadius: 6))
                .rotationEffect(.degrees(-2))
                .shadow(color: .black.opacity(0.5), radius: 24, y: 14)

                HStack(spacing: 10) {
                    let image = Image(uiImage: result.photo)
                    ShareLink(item: image, preview: SharePreview("\(result.species.name) in Mirrorlings", image: image)) {
                        Text("Share")
                            .font(.label(17))
                            .foregroundStyle(Color.chrome)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 15)
                            .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).stroke(Color.chrome.opacity(0.35)))
                    }
                    Button("Keep catching") { game.dismissCard() }
                        .buttonStyle(StickerButtonStyle())
                }
            }
            .padding(.horizontal, 28)
            .frame(maxWidth: 400)
        }
    }
}
