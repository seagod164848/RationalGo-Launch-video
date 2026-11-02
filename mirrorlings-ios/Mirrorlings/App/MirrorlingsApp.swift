import SwiftUI

@main
struct MirrorlingsApp: App {
    @State private var game = GameModel()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(game)
                .preferredColorScheme(.dark)
                .statusBarHidden()
                .task { await game.drop.refreshIfAllowed() }
        }
    }
}

struct ContentView: View {
    @Environment(GameModel.self) private var game

    var body: some View {
        @Bindable var game = game
        ZStack {
            Color.ink.ignoresSafeArea()

            if game.phase != .intro {
                MirrorView(game: game).ignoresSafeArea()
                EncounterBubble().ignoresSafeArea()
                HUDView()
            }

            if game.phase == .intro {
                IntroView().transition(.opacity)
            }

            if game.phase == .card, let result = game.lastCatch {
                CatchCardView(result: result)
                    .transition(.opacity.combined(with: .scale(scale: 0.92)))
            }
        }
        .animation(.spring(duration: 0.4), value: game.phase)
        .fullScreenCover(isPresented: $game.showShelf) {
            ShelfView().environment(game)
        }
        .sensoryFeedback(.success, trigger: game.catchPulse)
        .sensoryFeedback(.impact(weight: .medium), trigger: game.stepPulse)
    }
}
