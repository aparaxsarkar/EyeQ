import Foundation

enum APIError: LocalizedError {
    case invalidURL
    case requestFailed(Int)
    case unreachableServer(String)

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "The API URL is invalid."
        case .requestFailed(let statusCode):
            return "The server responded with status \(statusCode)."
        case .unreachableServer(let baseURL):
            return "Could not reach \(baseURL). Use the public EyeQ URL for phone testing, or keep both devices on the same Wi‑Fi and allow Local Network access for EyeQ."
        }
    }
}

struct APIClient {
    private let decoder = JSONDecoder()
    private let encoder = JSONEncoder()

    func fetchOverview(baseURL: String) async throws -> OverviewResponse {
        try await send(path: "/mobile/v1/overview", baseURL: baseURL)
    }

    func fetchIncidents(baseURL: String) async throws -> [Incident] {
        let response: IncidentsResponse = try await send(path: "/mobile/v1/incidents?limit=50", baseURL: baseURL)
        return response.items
    }

    func fetchIncident(baseURL: String, id: Int) async throws -> Incident {
        try await send(path: "/mobile/v1/incidents/\(id)", baseURL: baseURL)
    }

    func registerDevice(baseURL: String, token: String, deviceName: String, appVersion: String) async throws {
        let payload = DeviceRegistrationPayload(
            platform: "ios",
            token: token,
            deviceName: deviceName,
            appVersion: appVersion,
            notificationsEnabled: true
        )
        _ = try await send(
            path: "/mobile/v1/devices",
            baseURL: baseURL,
            method: "POST",
            body: try encoder.encode(payload)
        ) as EmptyResponse
    }

    func sendTestNotification(baseURL: String) async throws -> TestNotificationResponse {
        try await send(
            path: "/mobile/v1/notifications/test",
            baseURL: baseURL,
            method: "POST"
        )
    }

    private func send<T: Decodable>(
        path: String,
        baseURL: String,
        method: String = "GET",
        body: Data? = nil
    ) async throws -> T {
        guard let url = URL(string: normalizedBaseURL(baseURL) + path) else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.timeoutInterval = 15
        if let body {
            request.httpBody = body
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        }

        let data: Data
        let response: URLResponse
        do {
            (data, response) = try await URLSession.shared.data(for: request)
        } catch {
            throw APIError.unreachableServer(normalizedBaseURL(baseURL))
        }
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.requestFailed(-1)
        }
        guard (200 ..< 300).contains(httpResponse.statusCode) else {
            throw APIError.requestFailed(httpResponse.statusCode)
        }
        return try decoder.decode(T.self, from: data)
    }

    private func normalizedBaseURL(_ baseURL: String) -> String {
        baseURL.trimmingCharacters(in: .whitespacesAndNewlines).trimmingCharacters(in: CharacterSet(charactersIn: "/"))
    }
}

private struct EmptyResponse: Decodable {}
