import AppKit

enum FigNestMenu {
    static func make(target: AnyObject, about: Selector, settings: Selector) -> NSMenu {
        let menu = NSMenu(title: "FigNest")
        let aboutItem = NSMenuItem(title: "关于 FigNest", action: about, keyEquivalent: "")
        aboutItem.target = target
        menu.addItem(aboutItem)
        menu.addItem(.separator())
        let settingsItem = NSMenuItem(title: "设置…", action: settings, keyEquivalent: ",")
        settingsItem.keyEquivalentModifierMask = [.command]
        settingsItem.target = target
        menu.addItem(settingsItem)
        menu.addItem(.separator())
        let servicesItem = NSMenuItem(title: "服务", action: nil, keyEquivalent: "")
        servicesItem.submenu = NSMenu(title: "服务")
        menu.addItem(servicesItem)
        menu.addItem(.separator())
        menu.addItem(withTitle: "隐藏 FigNest", action: #selector(NSApplication.hide(_:)), keyEquivalent: "h")
        let hideOthers = NSMenuItem(title: "隐藏其他", action: #selector(NSApplication.hideOtherApplications(_:)), keyEquivalent: "h")
        hideOthers.keyEquivalentModifierMask = [.command, .option]
        menu.addItem(hideOthers)
        menu.addItem(withTitle: "全部显示", action: #selector(NSApplication.unhideAllApplications(_:)), keyEquivalent: "")
        menu.addItem(.separator())
        menu.addItem(withTitle: "退出 FigNest", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        return menu
    }
}
