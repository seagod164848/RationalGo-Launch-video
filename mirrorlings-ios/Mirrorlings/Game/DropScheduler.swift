import Foundation
import UserNotifications

/// The Drop: one two-minute window a day, at the same local time for every
/// player, picked from the date so no server is needed.
final class DropScheduler {
    static let window: TimeInterval = 120
    private let calendar = Calendar.current
    #if DEBUG
    var debugStart: Date?
    #endif

    /// Start of the day's Drop, somewhere between 10:00 and 20:59 local time.
    func dropStart(on day: Date) -> Date {
        let c = calendar.dateComponents([.year, .month, .day], from: day)
        let seed = (c.year ?? 0) * 10_000 + (c.month ?? 0) * 100 + (c.day ?? 0)
        var x = UInt64(seed) &* 0x9E37_79B9_7F4A_7C15
        x ^= x >> 31
        x = x &* 0xBF58_476D_1CE4_E5B9
        x ^= x >> 27
        let minutes = Int(x % 660)
        return calendar.startOfDay(for: day).addingTimeInterval(TimeInterval((10 * 60 + minutes) * 60))
    }

    /// Seconds left in a live Drop, or nil when there isn't one.
    func secondsLeft(now: Date = .now) -> Int? {
        var start = dropStart(on: now)
        #if DEBUG
        if let d = debugStart, now.timeIntervalSince(d) < Self.window { start = d }
        #endif
        let elapsed = now.timeIntervalSince(start)
        guard elapsed >= 0, elapsed < Self.window else { return nil }
        return Int((Self.window - elapsed).rounded(.up))
    }

    /// Ask for notification permission and schedule the next week of Drops.
    @discardableResult
    func enableAlerts() async -> Bool {
        let center = UNUserNotificationCenter.current()
        let granted = (try? await center.requestAuthorization(options: [.alert, .sound])) ?? false
        guard granted else { return false }
        await schedule(center)
        return true
    }

    /// Re-fill the week ahead if the player already allowed alerts.
    func refreshIfAllowed() async {
        let center = UNUserNotificationCenter.current()
        let settings = await center.notificationSettings()
        guard settings.authorizationStatus == .authorized else { return }
        await schedule(center)
    }

    private func schedule(_ center: UNUserNotificationCenter) async {
        let ids = (0..<8).map { "drop-\($0)" }
        center.removePendingNotificationRequests(withIdentifiers: ids)
        for offset in 0..<8 {
            guard let day = calendar.date(byAdding: .day, value: offset, to: .now) else { continue }
            let start = dropStart(on: day)
            guard start > .now else { continue }
            let content = UNMutableNotificationContent()
            content.title = "The Drop is live"
            content.body = "Two minutes. Open the mirror."
            content.sound = .default
            let when = calendar.dateComponents([.year, .month, .day, .hour, .minute], from: start)
            let request = UNNotificationRequest(identifier: ids[offset], content: content,
                                                trigger: UNCalendarNotificationTrigger(dateMatching: when, repeats: false))
            try? await center.add(request)
        }
    }
}
