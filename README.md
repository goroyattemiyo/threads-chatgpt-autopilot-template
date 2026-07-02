# Threads ChatGPT Autopilot Template

ChatGPT／Codexとの会話から投稿予定を管理し、GitHub ActionsとThreads APIで自動投稿するための汎用テンプレートです。

> 現在は **v0.1・販売前検証中** です。テストが完了するまで、本番アカウントでの利用は想定していません。

## 対応範囲

現時点の対応SNSは **Threadsのみ** です。

- テキスト投稿
- 画像付き投稿
- ツリー形式の投稿
- 投稿日時・投稿枠の管理
- 投稿予定と投稿履歴のYAML管理
- 投稿結果・エラーの書き戻し
- ChatGPT／Codexによる投稿追加・修正・履歴検索

X、Instagram、Facebook、Bluesky、TikTokなどには対応していません。

## リポジトリ構成

### テキスト投稿のみ

このPrivateリポジトリ1つで運用できます。

### 画像付き投稿

次の2リポジトリ構成を標準とします。

1. このPrivateリポジトリ：投稿予定、履歴、Actions、Secrets
2. 顧客所有のPublic画像リポジトリ：Threadsから取得する投稿用画像のみ

Public画像リポジトリへ入れた画像は、インターネット上から閲覧できます。

## ディレクトリ

```text
.github/workflows/       GitHub Actions
config/service.yml       顧客別の公開可能な設定
incoming/images/         画像の投入場所
posts/schedules/         週別の投稿予定
posts/posted_log.yml     投稿済み履歴
posts/assets.yml         処理済み画像の履歴
src/                     Python実装
docs/                    データ形式・安全方針
```

## 投稿時刻

`config/service.yml`の`posting.time_slots`で投稿枠を定義します。

```yaml
posting:
  time_slots:
    morning: "07:00"
    noon: "12:00"
    evening: "20:00"
```

GitHub Actionsは10分ごとに起動し、現在時刻に該当する投稿枠だけを確認します。

GitHub Actionsのschedule実行は遅れる場合があるため、秒単位・分単位の厳密な時刻保証はしません。

## 必要なGitHub Secrets

| Secret | 用途 |
|---|---|
| `THREADS_ACCESS_TOKEN` | Threads長期アクセストークン |
| `THREADS_USER_ID` | ThreadsユーザーID |
| `ASSETS_REPO_TOKEN` | Public画像リポジトリへの書き込み。画像投稿時のみ |

Secretsの実値を、コード、YAML、Issue、チャット、メールへ保存しないでください。

## 画像投稿時のGitHub Variables

| Variable | 例 |
|---|---|
| `ASSETS_REPO_FULL_NAME` | `owner/threads-autopilot-assets` |
| `ASSETS_REPO_BRANCH` | `main` |

画像用トークンは、画像リポジトリ1つだけに`Contents: Read and write`を許可したFine-grained Personal Access Tokenを使用します。

## 初期設定

1. `TEMPLATE_SETUP.md`を読む
2. `config/service.yml`を顧客環境へ合わせる
3. 利用者本人がGitHub Secretsを登録する
4. 画像投稿時はPublic画像リポジトリとVariablesを設定する
5. `Test Threads Connection`を実行する
6. dry runで投稿予定を確認する
7. 少数のテスト投稿で動作確認する

## 投稿データ

投稿形式は`docs/POST_SCHEMA.md`を参照してください。

投稿対象は、原則として以下をすべて満たす項目です。

- 当日の日付と投稿枠が一致
- `status: ready`
- `threads_post_id`が空

投稿成功後は`status: posted`、投稿ID、投稿日時を自動記録します。

## 安全方針

- パスワードやトークンを運営者へ渡さない
- 利用者本人がSecretsへ入力する
- 投稿管理リポジトリはPrivateにする
- Public画像リポジトリへ投稿本文・履歴・顧客情報を置かない
- 画像は利用権利を持つものだけを使用する
- 契約終了時は運営者権限と画像用トークンを失効する

## 現在の未検証項目

- 新規顧客アカウントへの導入リハーサル
- Threads API認証エラー時の全パターン
- ツリー途中失敗後の復旧
- GitHub Actionsの重複実行耐性
- Public画像URLの長期運用
- 10分間隔の投稿時刻判定

販売前チェックが完了するまで、本リポジトリを完成品として配布しません。
