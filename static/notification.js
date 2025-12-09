// 通知管理システム - 忘却曲線に基づくしつこいリマインダー

class ReviewNotificationManager {
    constructor() {
        this.swRegistration = null;
        this.isSupported = 'serviceWorker' in navigator && 'Notification' in window;
        this.notificationSettings = this.loadSettings();
    }

    // 設定を読み込み
    loadSettings() {
        const defaults = {
            enabled: true,
            aggressiveMode: true, // しつこいモード
            reminderIntervals: [0, 15, 30, 60], // 分単位での再通知間隔
            quietHoursStart: 23, // 静かな時間の開始（23時）
            quietHoursEnd: 7,    // 静かな時間の終了（7時）
            soundEnabled: true
        };
        
        try {
            const saved = localStorage.getItem('notificationSettings');
            return saved ? { ...defaults, ...JSON.parse(saved) } : defaults;
        } catch {
            return defaults;
        }
    }

    // 設定を保存
    saveSettings() {
        localStorage.setItem('notificationSettings', JSON.stringify(this.notificationSettings));
    }

    // Service Workerを登録
    async init() {
        if (!this.isSupported) {
            console.log('通知はこのブラウザでサポートされていません');
            return false;
        }

        try {
            this.swRegistration = await navigator.serviceWorker.register('/static/sw.js');
            console.log('Service Worker登録成功');
            
            // 定期的な復習チェックを登録（対応ブラウザのみ）
            if ('periodicSync' in this.swRegistration) {
                try {
                    await this.swRegistration.periodicSync.register('review-check', {
                        minInterval: 60 * 60 * 1000 // 1時間ごと
                    });
                } catch (e) {
                    console.log('定期同期の登録に失敗:', e);
                }
            }
            
            return true;
        } catch (error) {
            console.error('Service Worker登録失敗:', error);
            return false;
        }
    }

    // 通知許可をリクエスト
    async requestPermission() {
        if (!this.isSupported) {
            return 'unsupported';
        }

        const permission = await Notification.requestPermission();
        
        if (permission === 'granted') {
            this.showWelcomeNotification();
        }
        
        return permission;
    }

    // ウェルカム通知
    showWelcomeNotification() {
        if (this.swRegistration) {
            this.swRegistration.showNotification('通知が有効になりました！', {
                body: 'これで復習の時間を逃しません。絶対に覚えましょう！💪',
                icon: '/static/icon-192.png',
                tag: 'welcome'
            });
        }
    }

    // 静かな時間かどうかチェック
    isQuietHours() {
        const now = new Date();
        const hour = now.getHours();
        const { quietHoursStart, quietHoursEnd } = this.notificationSettings;
        
        if (quietHoursStart > quietHoursEnd) {
            // 例: 23時〜7時
            return hour >= quietHoursStart || hour < quietHoursEnd;
        } else {
            return hour >= quietHoursStart && hour < quietHoursEnd;
        }
    }

    // ローカル通知をスケジュール（忘却曲線ベース）
    scheduleReviewNotifications(item) {
        if (!this.notificationSettings.enabled) return;
        
        // 忘却曲線に基づく通知タイミング（分単位）
        // 最初の復習は特に重要なので頻繁に
        const timings = [
            { delay: 20, message: '20分経過！最初の復習タイムです' },
            { delay: 60, message: '1時間経過！記憶が薄れる前に復習' },
            { delay: 240, message: '4時間経過！忘れる前に確認しましょう' },
            { delay: 480, message: '8時間経過！寝る前に復習すると効果的' }
        ];

        timings.forEach(({ delay, message }) => {
            this.scheduleNotification({
                title: `📚 ${item.topic} の復習`,
                body: message,
                tag: `review-${item.id}-${delay}`,
                itemId: item.id,
                delay: delay * 60 * 1000 // ミリ秒に変換
            });
        });
    }

    // 通知をスケジュール
    scheduleNotification({ title, body, tag, itemId, delay }) {
        const scheduledTime = Date.now() + delay;
        
        // スケジュールをローカルストレージに保存
        const schedules = this.getScheduledNotifications();
        schedules.push({
            title, body, tag, itemId, scheduledTime,
            acknowledged: false
        });
        localStorage.setItem('scheduledNotifications', JSON.stringify(schedules));
        
        // 通知を設定
        setTimeout(() => {
            this.showAggressiveNotification({ title, body, tag, itemId });
        }, delay);
    }

    // スケジュールされた通知を取得
    getScheduledNotifications() {
        try {
            return JSON.parse(localStorage.getItem('scheduledNotifications') || '[]');
        } catch {
            return [];
        }
    }

    // しつこい通知を表示
    async showAggressiveNotification({ title, body, tag, itemId, attempt = 0 }) {
        // 静かな時間はスキップ（ただしキューに入れる）
        if (this.isQuietHours()) {
            console.log('静かな時間のため通知を延期');
            // 静かな時間が終わったら通知
            const now = new Date();
            const endHour = this.notificationSettings.quietHoursEnd;
            let delayMs;
            
            if (now.getHours() < endHour) {
                delayMs = (endHour - now.getHours()) * 60 * 60 * 1000;
            } else {
                delayMs = (24 - now.getHours() + endHour) * 60 * 60 * 1000;
            }
            
            setTimeout(() => {
                this.showAggressiveNotification({ title, body, tag, itemId, attempt });
            }, delayMs);
            return;
        }

        // 既に確認済みかチェック
        const schedules = this.getScheduledNotifications();
        const schedule = schedules.find(s => s.tag === tag);
        if (schedule && schedule.acknowledged) {
            return;
        }

        // 通知を表示
        if (this.swRegistration && Notification.permission === 'granted') {
            await this.swRegistration.showNotification(title, {
                body: body + (attempt > 0 ? ` (${attempt + 1}回目のリマインド)` : ''),
                icon: '/static/icon-192.png',
                badge: '/static/icon-192.png',
                tag: tag,
                renotify: true,
                requireInteraction: true,
                vibrate: this.getVibrationPattern(attempt),
                actions: [
                    { action: 'review', title: '✅ 復習する' },
                    { action: 'snooze', title: '⏰ 後で' }
                ],
                data: { itemId, attempt }
            });
        }

        // しつこいモードが有効なら再通知をスケジュール
        if (this.notificationSettings.aggressiveMode && attempt < 5) {
            const intervals = this.notificationSettings.reminderIntervals;
            const nextInterval = intervals[Math.min(attempt, intervals.length - 1)] || 30;
            
            setTimeout(() => {
                // 再度確認済みかチェック
                const currentSchedules = this.getScheduledNotifications();
                const currentSchedule = currentSchedules.find(s => s.tag === tag);
                if (!currentSchedule || !currentSchedule.acknowledged) {
                    this.showAggressiveNotification({
                        title: title + ' ⚠️',
                        body: 'まだ復習していません！今すぐ確認しましょう',
                        tag,
                        itemId,
                        attempt: attempt + 1
                    });
                }
            }, nextInterval * 60 * 1000);
        }
    }

    // バイブレーションパターン（回数が増えるほど激しく）
    getVibrationPattern(attempt) {
        const patterns = [
            [200, 100, 200],
            [200, 100, 200, 100, 200],
            [300, 100, 300, 100, 300, 100, 300],
            [500, 100, 500, 100, 500, 100, 500, 100, 500],
            [100, 50, 100, 50, 100, 50, 100, 50, 100, 50, 500, 100, 500]
        ];
        return patterns[Math.min(attempt, patterns.length - 1)];
    }

    // 通知を確認済みにする
    acknowledgeNotification(tag) {
        const schedules = this.getScheduledNotifications();
        const schedule = schedules.find(s => s.tag === tag);
        if (schedule) {
            schedule.acknowledged = true;
            localStorage.setItem('scheduledNotifications', JSON.stringify(schedules));
        }
    }

    // 今日の復習アラートを設定
    async scheduleAllTodayReviews(items) {
        for (const item of items) {
            // 即座に通知
            await this.showAggressiveNotification({
                title: `📖 「${item.topic}」を復習しましょう`,
                body: '今日が復習予定日です！',
                tag: `today-${item.id}`,
                itemId: item.id
            });
        }
    }

    // 定期チェック開始
    startPeriodicCheck(intervalMinutes = 30) {
        // 初回チェック
        this.checkAndNotify();
        
        // 定期的にチェック
        setInterval(() => {
            this.checkAndNotify();
        }, intervalMinutes * 60 * 1000);
    }

    // 復習項目をチェックして通知
    async checkAndNotify() {
        try {
            const response = await fetch('/api/pending-reviews');
            const data = await response.json();
            
            if (data.count > 0 && !this.isQuietHours()) {
                await this.showAggressiveNotification({
                    title: `🔔 ${data.count}件の復習待ち`,
                    body: '忘れる前に今すぐ復習しましょう！',
                    tag: 'pending-check',
                    itemId: null
                });
            }
        } catch (error) {
            console.error('復習チェック失敗:', error);
        }
    }
}

// グローバルインスタンス
const notificationManager = new ReviewNotificationManager();

// ページ読み込み時に初期化
document.addEventListener('DOMContentLoaded', async () => {
    await notificationManager.init();
    
    // 通知許可ボタンがあれば設定
    const enableBtn = document.getElementById('enable-notifications');
    if (enableBtn) {
        enableBtn.addEventListener('click', async () => {
            const permission = await notificationManager.requestPermission();
            if (permission === 'granted') {
                enableBtn.textContent = '✅ 通知有効';
                enableBtn.disabled = true;
                // 定期チェック開始
                notificationManager.startPeriodicCheck(30);
            } else if (permission === 'denied') {
                alert('通知がブロックされています。ブラウザの設定から許可してください。');
            }
        });
        
        // 既に許可されている場合
        if (Notification.permission === 'granted') {
            enableBtn.textContent = '✅ 通知有効';
            enableBtn.disabled = true;
            notificationManager.startPeriodicCheck(30);
        }
    }
    
    // しつこいモードトグル
    const aggressiveToggle = document.getElementById('aggressive-mode');
    if (aggressiveToggle) {
        aggressiveToggle.checked = notificationManager.notificationSettings.aggressiveMode;
        aggressiveToggle.addEventListener('change', () => {
            notificationManager.notificationSettings.aggressiveMode = aggressiveToggle.checked;
            notificationManager.saveSettings();
        });
    }
});
