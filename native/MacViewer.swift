import AppKit
import Foundation
import WebKit

final class ViewerApplication: NSObject, NSApplicationDelegate, WKUIDelegate, WKNavigationDelegate {
    private var window: NSWindow?
    private var webView: WKWebView?
    private var serverPort: Int?
    private var pageReady = false
    private var pendingSettings = false

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        let menu = NSMenu()
        let appItem = NSMenuItem()
        let appMenu = FigNestMenu.make(target: self, about: #selector(showAbout(_:)), settings: #selector(showSettings(_:)))
        appItem.submenu = appMenu
        NSApp.servicesMenu = appMenu.items.first(where: { $0.title == "服务" })?.submenu
        menu.addItem(appItem)
        let editItem = NSMenuItem()
        let editMenu = NSMenu(title: "编辑")
        editMenu.addItem(withTitle: "撤销", action: Selector(("undo:")), keyEquivalent: "z")
        editMenu.addItem(NSMenuItem.separator())
        editMenu.addItem(withTitle: "剪切", action: #selector(NSText.cut(_:)), keyEquivalent: "x")
        editMenu.addItem(withTitle: "复制", action: #selector(NSText.copy(_:)), keyEquivalent: "c")
        editMenu.addItem(withTitle: "粘贴", action: #selector(NSText.paste(_:)), keyEquivalent: "v")
        editItem.submenu = editMenu
        menu.addItem(editItem)
        let viewItem = NSMenuItem()
        let viewMenu = NSMenu(title: "查看")
        let reloadItem = NSMenuItem(title: "刷新", action: #selector(reloadPage(_:)), keyEquivalent: "r")
        reloadItem.target = self
        viewMenu.addItem(reloadItem)
        viewItem.submenu = viewMenu
        menu.addItem(viewItem)
        NSApp.mainMenu = menu

        guard let url = startOrReuseServer() else { return }
        serverPort = url.port
        let configuration = WKWebViewConfiguration()
        configuration.defaultWebpagePreferences.allowsContentJavaScript = true
        let web = WKWebView(frame: .zero, configuration: configuration)
        web.uiDelegate = self
        web.navigationDelegate = self
        self.webView = web
        let frame = NSRect(x: 0, y: 0, width: 1220, height: 800)
        let window = NSWindow(contentRect: frame, styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = "FigNest · 图匣"
        window.minSize = NSSize(width: 720, height: 520)
        window.center()
        window.contentView = web
        window.makeKeyAndOrderFront(nil)
        self.window = window
        web.load(URLRequest(url: url))
        NSApp.activate(ignoringOtherApps: true)
    }

    @objc private func reloadPage(_ sender: Any?) {
        pageReady = false
        webView?.reload()
    }

    @objc private func showAbout(_ sender: Any?) {
        let info = Bundle.main.infoDictionary ?? [:]
        let credits = NSAttributedString(string: "Organize, compare and present your visual work.\nQiushan · @QiushanHuang",
                                         attributes: [.font: NSFont.systemFont(ofSize: 12)])
        NSApp.orderFrontStandardAboutPanel(options: [
            .applicationName: "FigNest · 图匣",
            .applicationVersion: info["CFBundleShortVersionString"] as? String ?? "",
            .version: info["CFBundleVersion"] as? String ?? "",
            .credits: credits
        ])
        NSApp.activate(ignoringOtherApps: true)
    }

    @objc private func showSettings(_ sender: Any?) {
        window?.makeKeyAndOrderFront(nil)
        guard pageReady else { pendingSettings = true; return }
        // Only dispatch a fixed UI event into the bound local application page.
        webView?.evaluateJavaScript("window.dispatchEvent(new CustomEvent('fignest:settings'));")
    }

    func webView(_ webView: WKWebView, didStartProvisionalNavigation navigation: WKNavigation!) {
        pageReady = false
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        pageReady = true
        if pendingSettings { pendingSettings = false; showSettings(nil) }
    }

    private func startOrReuseServer() -> URL? {
        guard let resources = Bundle.main.resourceURL else { return nil }
        let backend = resources.appendingPathComponent("backend/library-backend")
        let data = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Pictures/ImageCollectionViewer")
        let process = Process()
        process.executableURL = backend
        process.arguments = ["--data", data.path, "launch", "--no-open"]
        let stdout = Pipe()
        let stderr = Pipe()
        process.standardOutput = stdout
        process.standardError = stderr
        do {
            try process.run()
            process.waitUntilExit()
            let output = stdout.fileHandleForReading.readDataToEndOfFile()
            let errorOutput = stderr.fileHandleForReading.readDataToEndOfFile()
            if process.terminationStatus == 0,
               let response = try JSONSerialization.jsonObject(with: output) as? [String: String],
               let address = response["url"],
               let url = URL(string: address),
               url.scheme == "http", url.host == "127.0.0.1" {
                return url
            }
            let message = String(data: errorOutput, encoding: .utf8) ?? "图库服务没有返回可用地址。"
            showError(message)
        } catch {
            showError("无法启动图库服务：\(error.localizedDescription)")
        }
        return nil
    }

    private func showError(_ message: String) {
        let alert = NSAlert()
        alert.messageText = "图匣暂时无法打开"
        alert.informativeText = message
        alert.alertStyle = .warning
        alert.runModal()
        NSApp.terminate(nil)
    }

    func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters,
                 initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping ([URL]?) -> Void) {
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.canChooseDirectories = parameters.allowsDirectories
        panel.canChooseFiles = true
        panel.begin { response in
            completionHandler(response == .OK ? panel.urls : nil)
        }
    }

    func webView(_ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
                 for navigationAction: WKNavigationAction, windowFeatures: WKWindowFeatures) -> WKWebView? {
        if let url = navigationAction.request.url,
           url.scheme == "http", url.host == "127.0.0.1", url.port == serverPort {
            NSWorkspace.shared.open(url)
        }
        return nil
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                 decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let requestURL = navigationAction.request.url else { decisionHandler(.cancel); return }
        if requestURL.host == "127.0.0.1",
           requestURL.port == serverPort,
           requestURL.scheme == "http" {
            decisionHandler(.allow)
        } else {
            decisionHandler(.cancel)
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool {
        return true
    }
}

@main struct FigNestEntry {
    static func main() {
        let application = NSApplication.shared
        let delegate = ViewerApplication()
        application.delegate = delegate
        withExtendedLifetime(delegate) { application.run() }
    }
}
