import Foundation

@main struct PolicyTests {
    static func main() {
        let port = 8879
        for raw in ["http://127.0.0.1:8879/media/a", "blob:http://127.0.0.1:8879/uuid"] {
            precondition(ImageToolPolicy.allowsDownload(URL(string: raw)!, port: port))
        }
        for raw in ["blob:https://example.com/a", "http://127.0.0.1:8880/a",
                    "blob:http://127.0.0.1:8880/a", "file:///tmp/a", "data:text/html,evil",
                    "https://127.0.0.1:8879/a", "http://user@127.0.0.1:8879/a"] {
            precondition(!ImageToolPolicy.allowsDownload(URL(string: raw)!, port: port))
        }
        precondition(!ImageToolPolicy.allowsDownload(URL(string: "http://127.0.0.1:8879/a")!, port: nil))
        print("native image downloads: bound local HTTP/blob origin PASS")
    }
}
