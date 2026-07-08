# 投稿エラー復旧手順

## 最優先ルール

- パスワード、アクセストークン、GitHubトークン、Secrets、二段階認証コードをチャット・Issue・ログへ貼らない
- `error`またはcheckpoint失敗の投稿を、原因確認なしで`ready`へ戻さない
- Threads上に投稿が存在する可能性がある場合は、先に実画面・Actionsログ・復旧Artifactを照合する
- `posted`の投稿ID・投稿日時・履歴を推測で変更しない

## YAMLへ記録される項目

失敗時は可能な範囲で次を記録する。

```yaml
status: error
error: sanitized error message
error_kind: configuration | authentication | image_url | api
error_code: "190"
error_at: 2026-07-08T19:30:00+09:00
recovery_action: operator-facing recovery instruction
```

GitHubへのcheckpoint保存に失敗した場合：

```yaml
checkpoint_error: sanitized checkpoint error
checkpoint_failed_at: 2026-07-08T19:30:00+09:00
recovery_action: Do not rerun...
```

## configuration

対象例：

- `THREADS_ACCESS_TOKEN`未設定
- `THREADS_USER_ID`未設定
- 必須GitHub Secretの登録漏れ

復旧：

1. 利用者本人がGitHub Secrets画面を開く
2. 値入力中は画面共有を停止する
3. 必要なSecret名へ値を登録する
4. 値そのものは再表示・共有しない
5. 対象投稿IDと`threads_post_id`が空であることを確認する
6. `status: error`から`status: ready`へ明示的に変更する
7. 対象`post_id`だけを再実行する

## authentication

対象例：

- 無効なアクセストークン
- 期限切れアクセストークン
- Threads Graph APIエラーコード`190`

復旧：

1. トークンの実値を共有しない
2. 利用者本人がトークンを再発行・更新する
3. GitHub Secretを利用者本人が更新する
4. `error_code`とマスク済み`error`を確認する
5. Threads上に同じ投稿が存在しないことを確認する
6. 対象投稿だけを`ready`へ戻す
7. 対象`post_id`だけを再実行する

漏えいが疑われる場合は、通常の再実行よりトークン失効・再発行を優先する。

## image_url

対象例：

- URLが404
- 認証なしで画像を取得できない
- URLが画像データを返さない
- Threads側が画像をダウンロードできない

復旧：

1. ブラウザのシークレットウィンドウなどでURLを確認する
2. ログインなしで画像だけが表示されることを確認する
3. 画像形式とURL切れを確認する
4. 必要ならPublic画像リポジトリへ再配置する
5. 投稿YAMLの`image_url`を修正する
6. Threads上に投稿が作成されていないことを確認する
7. 対象投稿だけを`ready`へ戻して再実行する

## api

認証・画像URL以外のThreads APIエラー。

1. マスク済み`error`とActionsログを確認する
2. Threadsアカウントの制限・API障害・文字数などを確認する
3. 投稿が作成された可能性を確認する
4. 原因と実投稿の有無が確定するまで再実行しない

## checkpoint

Threads投稿後にGitHubへ投稿ID・状態を保存できなかった可能性がある最重要ケース。

1. **再実行しない**
2. Threads実画面で投稿の有無と順序を確認する
3. Actionsログの以下を確認する
   - `schedule_id`
   - `root_post_id`
   - `reply_post_ids`
   - `CRITICAL_CHECKPOINT_FAILURE`
4. workflowの復旧Artifactをダウンロードする
5. Artifact内の投稿予定と`posts/posted_log.yml`を確認する
6. Threads上の実投稿IDを投稿YAMLへ反映する
7. 成功済みルート・返信を`thread_progress`へ反映する
8. 未完了部分だけを明示的に再開する

推測で空の投稿IDのまま再実行すると、二重投稿になる可能性がある。

## GitHub Actions障害

投稿workflow失敗時は、同名の開いているIssueへ追記するか新しいIssueを作成する。

Issueには以下だけを記載する。

- workflow runへのリンク
- 復旧Artifact名
- 対象投稿ID
- `error_kind`
- 投稿IDの有無
- 機密値を貼らない注意

投稿workflowは失敗時に次をArtifactとして14日間保存する。

- `posts/schedules/*.yml`
- `posts/posted_log.yml`

## Node・Actions警告

Nodeの移行警告、`punycode`、`url.parse()`などの非推奨警告だけで、各stepとjobが`success`の場合は失敗ではない。

古いNodeへ戻すために`ACTIONS_ALLOW_USE_UNSECURE_NODE_VERSION=true`を設定しない。利用中の公式Actionを対応版へ更新できる場合は更新し、それまではjobの結論を基準に判断する。
