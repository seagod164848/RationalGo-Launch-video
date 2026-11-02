import SwiftUI

struct IntroView: View {
    @Environment(GameModel.self) private var game
    @Environment(\.openURL) private var openURL
    @State private var alertsOn = false
    @State private var alertsDenied = false

    private let rules = [
        "A Mirrorling peeks over your shoulder and pulls a face. Copy it and hold it.",
        "Some only show up in daylight, late at night, or when a friend is in the frame.",
        "Once a day, The Drop: two minutes, same moment for everyone.",
    ]

    var body: some View {
        ZStack {
            RadialGradient(colors: [.plum, .ink], center: UnitPoint(x: 0.5, y: 0.15), startRadius: 0, endRadius: 520)
                .ignoresSafeArea()

            ScrollView {
                VStack(spacing: 22) {
                    Spacer(minLength: 40)

                    VStack(spacing: 10) {
                        Text("Mirrorlings")
                            .font(.display(54))
                            .foregroundStyle(Color.chrome)
                            .shadow(color: Color(hex: 0x6B55A8), radius: 0, x: 0, y: 4)
                            .shadow(color: .black.opacity(0.35), radius: 0, x: 0, y: 8)
                        Text("Little creatures live in your reflection. Copy the face they make to catch them.")
                            .font(.system(size: 18, weight: .medium, design: .rounded))
                            .foregroundStyle(Color.chrome)
                            .multilineTextAlignment(.center)
                            .frame(maxWidth: 320)
                    }

                    VStack(alignment: .leading, spacing: 10) {
                        ForEach(Array(rules.enumerated()), id: \.offset) { i, rule in
                            HStack(alignment: .firstTextBaseline, spacing: 10) {
                                Text(String(format: "%02d", i + 1)).font(.mono(12)).foregroundStyle(Color.sticker)
                                Text(rule).font(.system(size: 15)).foregroundStyle(Color.chromeDim)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                    }
                    .frame(maxWidth: 330, alignment: .leading)

                    VStack(spacing: 12) {
                        Button("Open the mirror") { game.start() }
                            .buttonStyle(StickerButtonStyle())

                        Button {
                            Task {
                                let ok = await game.drop.enableAlerts()
                                alertsOn = ok
                                alertsDenied = !ok
                            }
                        } label: {
                            Text(alertsOn ? "Drop alerts are on" : "Alert me when The Drop starts")
                                .font(.label(15, weight: .semibold))
                                .foregroundStyle(alertsOn ? Color.sticker : Color.chromeDim)
                                .underline(!alertsOn)
                        }
                        .disabled(alertsOn)

                        if alertsDenied {
                            Text("Notifications are off for Mirrorlings. You can turn them on in Settings.")
                                .font(.system(size: 13)).foregroundStyle(Color.chromeDim).multilineTextAlignment(.center)
                        }
                    }
                    .frame(maxWidth: 320)

                    if let problem = game.cameraProblem {
                        VStack(spacing: 8) {
                            Text(problem)
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundStyle(Color.sticker)
                                .multilineTextAlignment(.center)
                            Button("Open Settings") {
                                if let url = URL(string: UIApplication.openSettingsURLString) { openURL(url) }
                            }
                            .font(.label(14)).foregroundStyle(Color.chrome)
                        }
                        .frame(maxWidth: 320)
                    }

                    Text("SEASON 2026 · PROTOTYPE")
                        .font(.mono(10.5)).tracking(0.8)
                        .foregroundStyle(Color(hex: 0x7D71A0))
                        .padding(.top, 8)
                    Spacer(minLength: 24)
                }
                .padding(.horizontal, 20)
                .frame(maxWidth: .infinity)
            }
            .scrollBounceBehavior(.basedOnSize)
        }
    }
}
