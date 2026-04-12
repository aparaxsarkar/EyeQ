import Foundation
import UserNotifications
import UIKit

extension Notification.Name {
    static let careWatchDeviceToken = Notification.Name("careWatchDeviceToken")
    static let careWatchOpenIncident = Notification.Name("careWatchOpenIncident")
}

final class NotificationCoordinator: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        UNUserNotificationCenter.current().delegate = self
        return true
    }

    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        let token = deviceToken.map { String(format: "%02x", $0) }.joined()
        NotificationCenter.default.post(name: .careWatchDeviceToken, object: token)
    }

    func application(_ application: UIApplication, didFailToRegisterForRemoteNotificationsWithError error: Error) {
        print("Remote notification registration failed: \(error.localizedDescription)")
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .sound, .badge])
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        if let incidentID = response.notification.request.content.userInfo["incident_id"] as? Int {
            NotificationCenter.default.post(name: .careWatchOpenIncident, object: incidentID)
        } else if let incidentValue = response.notification.request.content.userInfo["incident_id"] as? String,
                  let incidentID = Int(incidentValue) {
            NotificationCenter.default.post(name: .careWatchOpenIncident, object: incidentID)
        }
        completionHandler()
    }
}
