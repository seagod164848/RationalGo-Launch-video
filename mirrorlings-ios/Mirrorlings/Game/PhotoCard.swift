import UIKit

/// Turns the AR snapshot into a 3:4 catch photo with a name stamp, ready to share.
enum PhotoCard {
    static func make(from snapshot: UIImage?, species: Species) -> UIImage {
        let source = snapshot.map(cropTo3x4) ?? placeholder()
        let size = source.size
        let format = UIGraphicsImageRendererFormat()
        format.scale = source.scale
        return UIGraphicsImageRenderer(size: size, format: format).image { _ in
            source.draw(in: CGRect(origin: .zero, size: size))
            let unit = size.width / 600

            let label = "\(species.name.uppercased()) · \(species.rarity.label.uppercased())"
            let labelAttrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.monospacedSystemFont(ofSize: 20 * unit, weight: .medium),
                .foregroundColor: UIColor(hex: species.rarity.hex),
            ]
            let labelSize = (label as NSString).size(withAttributes: labelAttrs)
            let pill = CGRect(x: 24 * unit, y: size.height - 72 * unit, width: labelSize.width + 32 * unit, height: 44 * unit)
            UIColor(white: 0.06, alpha: 0.72).setFill()
            UIBezierPath(roundedRect: pill, cornerRadius: 22 * unit).fill()
            (label as NSString).draw(at: CGPoint(x: pill.minX + 16 * unit, y: pill.midY - labelSize.height / 2),
                                     withAttributes: labelAttrs)

            let shadow = NSShadow()
            shadow.shadowColor = UIColor(white: 0, alpha: 0.5)
            shadow.shadowBlurRadius = 8 * unit
            let markAttrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.rounded(30 * unit, weight: .black),
                .foregroundColor: UIColor.white,
                .shadow: shadow,
            ]
            let mark = "Mirrorlings" as NSString
            let markSize = mark.size(withAttributes: markAttrs)
            mark.draw(at: CGPoint(x: size.width - markSize.width - 24 * unit, y: 22 * unit), withAttributes: markAttrs)
        }
    }

    /// Keep the top-middle of the portrait screen, where the face and creature are.
    private static func cropTo3x4(_ image: UIImage) -> UIImage {
        guard let cg = image.cgImage else { return image }
        let w = CGFloat(cg.width), h = CGFloat(cg.height)
        let targetH = min(h, w * 4 / 3)
        let y = max(0, min(h - targetH, h * 0.42 - targetH / 2))
        guard let cropped = cg.cropping(to: CGRect(x: 0, y: y, width: w, height: targetH).integral) else { return image }
        return UIImage(cgImage: cropped, scale: image.scale, orientation: image.imageOrientation)
    }

    private static func placeholder() -> UIImage {
        let size = CGSize(width: 600, height: 800)
        return UIGraphicsImageRenderer(size: size).image { ctx in
            UIColor(hex: 0x231A32).setFill()
            ctx.fill(CGRect(origin: .zero, size: size))
        }
    }
}
