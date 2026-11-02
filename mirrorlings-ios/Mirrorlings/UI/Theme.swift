import SwiftUI
import UIKit

extension Color {
    init(hex: UInt32, opacity: Double = 1) {
        self.init(.sRGB,
                  red: Double((hex >> 16) & 0xFF) / 255,
                  green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255,
                  opacity: opacity)
    }

    static let ink = Color(hex: 0x140F1D)
    static let ink2 = Color(hex: 0x231A32)
    static let plum = Color(hex: 0x3B2A5C)
    static let chrome = Color(hex: 0xF1ECFF)
    static let chromeDim = Color(hex: 0xB8AED6)
    static let sticker = Color(hex: 0xFFD84A)
    static let stickerInk = Color(hex: 0x2A1D00)
    static let stickerShadow = Color(hex: 0xB8951C)
    static let paper = Color(hex: 0xFBF8F1)
    static let paperInk = Color(hex: 0x1B1426)
    static let paperDim = Color(hex: 0x4A3F5C)
    static let alert = Color(hex: 0xD6336C)
}

extension UIColor {
    convenience init(hex: UInt32, alpha: CGFloat = 1) {
        self.init(red: CGFloat((hex >> 16) & 0xFF) / 255,
                  green: CGFloat((hex >> 8) & 0xFF) / 255,
                  blue: CGFloat(hex & 0xFF) / 255,
                  alpha: alpha)
    }
}

extension UIFont {
    static func rounded(_ size: CGFloat, weight: UIFont.Weight) -> UIFont {
        let base = UIFont.systemFont(ofSize: size, weight: weight)
        guard let descriptor = base.fontDescriptor.withDesign(.rounded) else { return base }
        return UIFont(descriptor: descriptor, size: size)
    }
}

extension Font {
    /// Chunky rounded display face: the vinyl-toy voice of the game.
    static func display(_ size: CGFloat) -> Font { .system(size: size, weight: .black, design: .rounded) }
    static func label(_ size: CGFloat, weight: Font.Weight = .heavy) -> Font { .system(size: size, weight: weight, design: .rounded) }
    static func mono(_ size: CGFloat) -> Font { .system(size: size, weight: .medium, design: .monospaced) }
}

/// The big yellow button with a hard drop shadow, like a sticker on a toy box.
struct StickerButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.label(18))
            .foregroundStyle(Color.stickerInk)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(Color.sticker, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
            .background(Color.stickerShadow, in: RoundedRectangle(cornerRadius: 18, style: .continuous).offset(y: configuration.isPressed ? 2 : 5))
            .offset(y: configuration.isPressed ? 3 : 0)
            .animation(.easeOut(duration: 0.08), value: configuration.isPressed)
    }
}

struct Chip: View {
    let text: String
    var lit = false

    var body: some View {
        Text(text.uppercased())
            .font(.mono(11))
            .tracking(0.6)
            .foregroundStyle(lit ? Color.stickerInk : Color.chromeDim)
            .padding(.horizontal, 10)
            .padding(.vertical, 7)
            .background {
                if lit { Capsule().fill(Color.sticker) } else { Capsule().fill(.ultraThinMaterial) }
            }
    }
}

struct RarityTag: View {
    let rarity: Rarity

    var body: some View {
        Text(rarity.label.uppercased())
            .font(.mono(10.5))
            .tracking(0.6)
            .foregroundStyle(Color.paperInk)
            .padding(.horizontal, 7)
            .padding(.vertical, 5)
            .background(rarity.color, in: RoundedRectangle(cornerRadius: 6, style: .continuous))
    }
}
