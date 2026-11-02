import Foundation
import Observation
import UIKit

/// The player's collection: one record and one photo per species, on disk.
@Observable
final class ShelfStore {
    struct Record: Codable {
        var count: Int
        var firstCaught: Date
        var lastCaught: Date
    }

    private(set) var records: [String: Record] = [:]
    @ObservationIgnored private var photos: [String: UIImage] = [:]
    private let dir: URL

    var count: Int { records.count }

    init() {
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first
            ?? FileManager.default.temporaryDirectory
        dir = base.appendingPathComponent("Shelf", isDirectory: true)
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        if let data = try? Data(contentsOf: indexURL),
           let saved = try? JSONDecoder().decode([String: Record].self, from: data) {
            records = saved
        }
    }

    private var indexURL: URL { dir.appendingPathComponent("shelf.json") }
    private func photoURL(_ id: String) -> URL { dir.appendingPathComponent("\(id).jpg") }

    func has(_ id: String) -> Bool { records[id] != nil }

    /// Saves a catch. Returns whether it is new and how many the player has.
    func record(_ species: Species, photo: UIImage) -> (isNew: Bool, count: Int) {
        let now = Date()
        let isNew = records[species.id] == nil
        var rec = records[species.id] ?? Record(count: 0, firstCaught: now, lastCaught: now)
        rec.count += 1
        rec.lastCaught = now
        records[species.id] = rec
        photos[species.id] = photo
        if let jpeg = photo.jpegData(compressionQuality: 0.85) {
            try? jpeg.write(to: photoURL(species.id), options: .atomic)
        }
        persist()
        return (isNew, rec.count)
    }

    func photo(for id: String) -> UIImage? {
        if let cached = photos[id] { return cached }
        guard let img = UIImage(contentsOfFile: photoURL(id).path) else { return nil }
        photos[id] = img
        return img
    }

    func reset() {
        for id in records.keys { try? FileManager.default.removeItem(at: photoURL(id)) }
        records = [:]
        photos = [:]
        persist()
    }

    private func persist() {
        if let data = try? JSONEncoder().encode(records) {
            try? data.write(to: indexURL, options: .atomic)
        }
    }
}
