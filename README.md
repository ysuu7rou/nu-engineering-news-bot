# 名古屋大学工学部・工学研究科 News 配信

配信先：Slackチャンネル `nuee-announce`。
専用Bot名の例：NUEE News Bot。

5分間隔で公式サイトの公開データを確認し、日本語の新着についてタイトルと記事リンクを1件ずつ配信します。初回は現在・過去の既存記事を記録するだけで、Slackには投稿しません。全カテゴリーを対象とします。AI APIは使用しません。

## 設置

1. 専用SlackアプリのIncoming Webhooksを有効にし、`nuee-announce`を選択してWebhookを作成します。既存のchip-news用Webhookは使用しません。
2. このフォルダーの内容（bot.py、.githubなど）を専用の公開GitHubリポジトリのルートへ登録します。WebhookやSlackの会話内容は登録しません。
3. リポジトリのSettings → Secrets and variables → Actionsで、`SLACK_WEBHOOK_URL`というRepository secretにWebhookを登録します。Webhookはチャットやリポジトリのファイルへ貼り付けません。
4. Actionsの「Nagoya Engineering News」を手動実行します。`Initialized`が表示されれば初期記録が完了です。以後は新着時だけ投稿します。

状態はリポジトリのdata/state.jsonへ保存します。処理は同時実行を防ぎ、投稿前後の状態を保存します。送信結果が不明の場合は再送せず停止します。Slackで該当記事の投稿を確認してから、投稿済みならそのIDをseenへ追加し、pendingをnullに戻します。未投稿と確認できた場合のみpendingをnullに戻して再開します。

GitHub Actionsの定期実行には遅延や実行欠落があり、公開から5分以内の配信は保証されません。停止中に公開され、検出前にサイトの公開データから削除された記事は取得できません。サイトの形式変更時には処理が停止します。

公開リポジトリの標準GitHub-hosted runnerを使用します。非公開へ変更するとActionsの無料枠・超過料金が適用されます。5分ごとの実行は1日288回、30日で8,640回です。公開リポジトリの定期実行はリポジトリに60日間活動がないと無効化されるため、長期休止時はActionsの状態を確認してください。

読み取りのみの確認：`python bot.py --preview`
