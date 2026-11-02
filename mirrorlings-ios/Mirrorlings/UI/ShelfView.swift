import SwiftUI

/// The collection. Locked slots say where to look instead of hiding it.
struct ShelfView: View {
    @Environment(GameModel.self) private var game
    @Environment(\.dismiss) private var dismiss
    @State private var confirmReset = false

    private let columns = [GridItem(.adaptive(minimum: 150), spacing: 12)]

    var body: some View {
        ZStack {
            Color.ink.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    HStack {
                        Text("Your shelf").font(.display(34)).foregroundStyle(Color.chrome)
                        Spacer()
                        Button("Back to the mirror") { dismiss() }
                            .font(.label(14))
                            .foregroundStyle(Color.chrome)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 10)
                            .background(Color.ink2, in: Capsule())
                    }

                    Text(subtitle).font(.system(size: 15)).foregroundStyle(Color.chromeDim)

                    LazyVGrid(columns: columns, spacing: 12) {
                        ForEach(Species.all) { species in
                            ShelfSlot(species: species,
                                      record: game.shelf.records[species.id],
                                      photo: game.shelf.photo(for: species.id))
                        }
                    }

                    if game.shelf.count > 0 {
                        Button("Clear my shelf") { confirmReset = true }
                            .font(.system(size: 14))
                            .foregroundStyle(Color(hex: 0x8E83AD))
                            .frame(maxWidth: .infinity)
                            .padding(.top, 16)
                    }
                }
                .padding(.horizontal, 18)
                .padding(.vertical, 20)
            }
        }
        .confirmationDialog("Clear every Mirrorling and photo on your shelf?", isPresented: $confirmReset, titleVisibility: .visible) {
            Button("Clear my shelf", role: .destructive) { game.shelf.reset() }
        }
    }

    private var subtitle: String {
        let n = game.shelf.count
        return n == 0
            ? "Nothing yet. Each locked slot tells you where to look."
            : "\(n) of \(Species.all.count) caught. Locked slots tell you where to look."
    }
}

struct ShelfSlot: View {
    let species: Species
    let record: ShelfStore.Record?
    let photo: UIImage?

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Color.clear
                .aspectRatio(3 / 4, contentMode: .fit)
                .overlay {
                    if let photo {
                        Image(uiImage: photo).resizable().scaledToFill()
                    } else {
                        ZStack {
                            Color(hex: 0x1A1426)
                            Circle()
                                .fill(species.rarity.color.opacity(0.18))
                                .frame(width: 84, height: 84)
                            Image(systemName: "questionmark")
                                .font(.system(size: 34, weight: .black, design: .rounded))
                                .foregroundStyle(species.rarity.color.opacity(0.7))
                        }
                    }
                }
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))

            HStack(alignment: .firstTextBaseline) {
                Text(record == nil ? "???" : species.name)
                    .font(.label(15))
                    .foregroundStyle(record == nil ? Color(hex: 0x8E83AD) : Color.chrome)
                Spacer(minLength: 4)
                if let record {
                    Text("×\(record.count)").font(.mono(11)).foregroundStyle(Color.chromeDim)
                }
            }

            HStack(spacing: 6) {
                Circle().fill(species.rarity.color).frame(width: 8, height: 8)
                Text(species.rarity.label).font(.system(size: 12.5)).foregroundStyle(Color.chromeDim)
            }

            Text(record == nil ? species.hint : species.lore)
                .font(.system(size: 12.5))
                .foregroundStyle(Color.chromeDim)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(10)
        .frame(maxHeight: .infinity, alignment: .top)
        .background(Color.ink2, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
    }
}
