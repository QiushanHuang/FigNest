import AppKit

@main struct MenuTests {
    static func main() {
        _ = NSApplication.shared
        let target = NSObject()
        let about = NSSelectorFromString("showAbout:")
        let settings = NSSelectorFromString("showSettings:")
        let menu = FigNestMenu.make(target: target, about: about, settings: settings)
        let settingItems = menu.items.filter { $0.action == settings }
        precondition(settingItems.count == 1)
        precondition(settingItems[0].keyEquivalent == ",")
        precondition(settingItems[0].keyEquivalentModifierMask == [.command])
        precondition(settingItems[0].target === target)
        precondition(menu.items.first?.action == about)
        precondition(menu.items.first?.title == "关于 FigNest")
        precondition(menu.items.contains { $0.action == #selector(NSApplication.terminate(_:)) && $0.keyEquivalent == "q" })
        print("Native menu: About, Settings Command-comma, responder targets and Quit PASS")
    }
}
