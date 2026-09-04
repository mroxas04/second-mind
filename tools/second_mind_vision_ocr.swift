import AppKit
import Foundation
import PDFKit
import Vision

struct Observation: Encodable {
    let text: String
    let confidence: Float
    let x: CGFloat
    let y: CGFloat
}

struct Result: Encodable {
    let version = 1
    let observations: [Observation]
}

func fail() -> Never { exit(1) }

guard CommandLine.arguments.count == 2 else { fail() }
let input = URL(fileURLWithPath: CommandLine.arguments[1])
let extensionName = input.pathExtension.lowercased()
let image: CGImage

if extensionName == "pdf" {
    guard let document = PDFDocument(url: input),
          !document.isEncrypted,
          document.pageCount == 1,
          let page = document.page(at: 0) else { fail() }
    let thumbnail = page.thumbnail(of: NSSize(width: 2550, height: 3300), for: .mediaBox)
    guard let rendered = thumbnail.cgImage(forProposedRect: nil, context: nil, hints: nil) else { fail() }
    image = rendered
} else {
    guard let source = NSImage(contentsOf: input),
          let loaded = source.cgImage(forProposedRect: nil, context: nil, hints: nil) else { fail() }
    image = loaded
}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.usesLanguageCorrection = true
let handler = VNImageRequestHandler(cgImage: image, options: [:])
do {
    try handler.perform([request])
} catch {
    fail()
}
let observations = (request.results ?? []).compactMap { observation -> Observation? in
    guard let candidate = observation.topCandidates(1).first,
          !candidate.string.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return nil }
    return Observation(text: candidate.string, confidence: candidate.confidence, x: observation.boundingBox.minX, y: observation.boundingBox.maxY)
}.sorted { left, right in
    left.y == right.y ? left.x < right.x : left.y > right.y
}
guard !observations.isEmpty,
      let data = try? JSONEncoder().encode(Result(observations: observations)) else { fail() }
FileHandle.standardOutput.write(data)
