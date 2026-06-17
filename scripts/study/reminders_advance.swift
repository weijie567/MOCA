#!/usr/bin/env swift

import EventKit
import Foundation

let listName = argValue("--list", default: "MOCA 30 Days")
let day = try resolveDay()
let dayTag = String(format: "[D%02d]", day)

func argValue(_ name: String, default defaultValue: String) -> String {
    let args = CommandLine.arguments
    if let index = args.firstIndex(of: name), index + 1 < args.count {
        return args[index + 1]
    }
    return defaultValue
}

func dailyDir() -> URL {
    URL(fileURLWithPath: "/Users/ming/projects/MOCA/study_plan/portfolio/daily", isDirectory: true)
}

func resolveDay() throws -> Int {
    let raw = argValue("--day", default: "auto")
    if raw != "auto" {
        guard let day = Int(raw), day >= 1, day <= 30 else {
            throw NSError(domain: "MOCAStudy", code: 1, userInfo: [NSLocalizedDescriptionKey: "day must be 1..30 or auto"])
        }
        return day
    }

    let configURL = dailyDir().appendingPathComponent("automation_config.json")
    let data = try Data(contentsOf: configURL)
    guard
        let json = try JSONSerialization.jsonObject(with: data) as? [String: Any],
        let startRaw = json["program_start_date"] as? String
    else {
        throw NSError(domain: "MOCAStudy", code: 2, userInfo: [NSLocalizedDescriptionKey: "missing program_start_date"])
    }
    let formatter = DateFormatter()
    formatter.dateFormat = "yyyy-MM-dd"
    guard let start = formatter.date(from: startRaw) else {
        throw NSError(domain: "MOCAStudy", code: 3, userInfo: [NSLocalizedDescriptionKey: "invalid program_start_date"])
    }
    let today = Calendar.current.startOfDay(for: Date())
    let startDay = Calendar.current.startOfDay(for: start)
    let offset = Calendar.current.dateComponents([.day], from: startDay, to: today).day ?? 0
    return min(max(offset + 1, 1), 30)
}

func requestReminderAccess(_ store: EKEventStore) async throws -> Bool {
    if #available(macOS 14.0, *) {
        return try await store.requestFullAccessToReminders()
    } else {
        return try await withCheckedThrowingContinuation { continuation in
            store.requestAccess(to: .reminder) { granted, error in
                if let error {
                    continuation.resume(throwing: error)
                } else {
                    continuation.resume(returning: granted)
                }
            }
        }
    }
}

func fetchReminders(store: EKEventStore, calendar: EKCalendar) async -> [EKReminder] {
    await withCheckedContinuation { continuation in
        let predicate = store.predicateForReminders(in: [calendar])
        store.fetchReminders(matching: predicate) { reminders in
            continuation.resume(returning: reminders ?? [])
        }
    }
}

func seq(_ title: String) -> Int? {
    guard let range = title.range(of: #"\[S(\d+)\]"#, options: .regularExpression) else {
        return nil
    }
    let token = String(title[range])
    let digits = token.filter { $0.isNumber }
    return Int(digits)
}

func appendLog(_ line: String) {
    let url = dailyDir().appendingPathComponent(String(format: "day%02d_log.md", day))
    var text = (try? String(contentsOf: url, encoding: .utf8)) ?? "# Day \(day) 执行日志\n"
    if !text.contains("## Reminders 自动推进记录") {
        if !text.hasSuffix("\n") { text += "\n" }
        text += "\n## Reminders 自动推进记录\n"
    }
    text += "- \(line)\n"
    try? text.write(to: url, atomically: true, encoding: .utf8)
}

func nowText() -> String {
    let formatter = DateFormatter()
    formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
    return formatter.string(from: Date())
}

do {
    let store = EKEventStore()
    let granted = try await requestReminderAccess(store)
    guard granted else {
        fputs("Reminders permission denied\n", stderr)
        exit(2)
    }

    guard let calendar = store.calendars(for: .reminder).first(where: { $0.title == listName }) else {
        print("list not found: \(listName)")
        exit(0)
    }

    let reminders = await fetchReminders(store: store, calendar: calendar)
        .filter { $0.title.contains(dayTag) && seq($0.title) != nil }
        .sorted { (seq($0.title) ?? 0) < (seq($1.title) ?? 0) }

    guard !reminders.isEmpty else {
        print("no reminders")
        exit(0)
    }

    guard let firstOpen = reminders.first(where: { !$0.isCompleted }) else {
        print("all complete")
        exit(0)
    }

    let currentTitle = firstOpen.title ?? ""
    if currentTitle.contains("[ACTIVE]") {
        print("active unchanged: \(currentTitle)")
        exit(0)
    }

    let updatedTitle = currentTitle.replacingOccurrences(of: "[WAIT]", with: "[ACTIVE]")
    firstOpen.title = updatedTitle
    firstOpen.dueDateComponents = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: Date())
    let alarm = EKAlarm(absoluteDate: Date())
    firstOpen.alarms = [alarm]
    firstOpen.notes = ((firstOpen.notes ?? "") + "\n实际开始：\(nowText())").trimmingCharacters(in: .whitespacesAndNewlines)

    try store.save(firstOpen, commit: true)
    let message = "\(nowText()) 激活 \(updatedTitle)"
    appendLog(message)
    print(message)
} catch {
    fputs("reminders advance error: \(error.localizedDescription)\n", stderr)
    exit(1)
}
