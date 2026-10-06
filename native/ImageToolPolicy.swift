import Foundation

enum ImageToolPolicy {
    static func allowsDownload(_ url: URL, port: Int?) -> Bool {
        guard let port else { return false }
        let address: URL?
        if url.scheme == "blob" {
            address = URL(string: String(url.absoluteString.dropFirst(5)))
        } else {
            address = url
        }
        return address?.scheme == "http" && address?.host == "127.0.0.1" &&
            address?.port == port && address?.user == nil && address?.password == nil
    }
}
