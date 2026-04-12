import SwiftUI

@main
struct EyeQ_IOSApp: App {
    @UIApplicationDelegateAdaptor(NotificationCoordinator.self) private var notificationCoordinator
    @StateObject private var store = AppStore()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(store)
                .onReceive(NotificationCenter.default.publisher(for: .eyeQDeviceToken)) { notification in
                    guard let token = notification.object as? String else { return }
                    Task {
                        await store.registerDeviceToken(token)
                    }
                }
                .onReceive(NotificationCenter.default.publisher(for: .eyeQOpenIncident)) { notification in
                    if let incidentID = notification.object as? Int {
                        Task {
                            await store.openIncident(id: incidentID)
                        }
                    }
                }
        }
    }
}
