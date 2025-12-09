// Service Worker for 復習タイマー
const CACHE_NAME = 'fukusyu-v1';
const urlsToCache = [
    '/',
    '/static/manifest.json'
];

// インストール時にキャッシュ
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => cache.addAll(urlsToCache))
    );
    self.skipWaiting();
});

// アクティベート時に古いキャッシュを削除
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

// プッシュ通知を受信
self.addEventListener('push', (event) => {
    let data = { title: '復習の時間です！', body: '暗記項目を復習しましょう' };
    
    if (event.data) {
        try {
            data = event.data.json();
        } catch (e) {
            data.body = event.data.text();
        }
    }

    const options = {
        body: data.body,
        icon: '/static/icon-192.png',
        badge: '/static/icon-192.png',
        vibrate: [200, 100, 200, 100, 200], // しつこいバイブレーション
        tag: data.tag || 'review-reminder',
        renotify: true, // 同じタグでも再通知
        requireInteraction: true, // 閉じるまで消えない！
        actions: [
            { action: 'review', title: '今すぐ復習する' },
            { action: 'snooze', title: '15分後にリマインド' }
        ],
        data: {
            itemId: data.itemId,
            url: data.url || '/'
        }
    };

    event.waitUntil(
        self.registration.showNotification(data.title, options)
    );
});

// 通知クリック時の処理
self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    
    const action = event.action;
    const data = event.notification.data;
    
    if (action === 'snooze') {
        // 15分後に再通知をスケジュール
        setTimeout(() => {
            self.registration.showNotification('復習の時間です！（リマインド）', {
                body: '先ほどスヌーズした項目を復習しましょう！',
                icon: '/static/icon-192.png',
                requireInteraction: true,
                vibrate: [300, 100, 300, 100, 300, 100, 300],
                tag: 'review-reminder-snooze'
            });
        }, 15 * 60 * 1000);
    } else {
        // アプリを開く
        event.waitUntil(
            clients.matchAll({ type: 'window' }).then((clientList) => {
                for (const client of clientList) {
                    if (client.url.includes('/') && 'focus' in client) {
                        return client.focus();
                    }
                }
                if (clients.openWindow) {
                    return clients.openWindow(data.url || '/');
                }
            })
        );
    }
});

// バックグラウンド同期
self.addEventListener('sync', (event) => {
    if (event.tag === 'check-reviews') {
        event.waitUntil(checkPendingReviews());
    }
});

async function checkPendingReviews() {
    try {
        const response = await fetch('/api/pending-reviews');
        const data = await response.json();
        
        if (data.count > 0) {
            self.registration.showNotification('復習が溜まっています！', {
                body: `${data.count}件の項目が復習待ちです。今すぐ確認しましょう！`,
                icon: '/static/icon-192.png',
                requireInteraction: true,
                vibrate: [200, 100, 200, 100, 200]
            });
        }
    } catch (error) {
        console.error('Failed to check pending reviews:', error);
    }
}

// 定期的なバックグラウンドフェッチ（対応ブラウザのみ）
self.addEventListener('periodicsync', (event) => {
    if (event.tag === 'review-check') {
        event.waitUntil(checkPendingReviews());
    }
});
