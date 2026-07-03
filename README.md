# Threads ChatGPT Autopilot Template

ChatGPT／Codex、通常のClaudeチャット、Claude Codeとの会話から投稿予定を管理し、GitHub ActionsとThreads APIで自動投稿するための汎用テンプレートです。

> 現在は **v0.1・販売前検証中** です。各AI環境の実動テストが完了するまで、本番向け完成品としては扱いません。

## 対応範囲

現時点の対応SNSは **Threadsのみ** です。

- テキスト投稿
- 画像付き投稿
- ツリー形式の投稿
- 投稿日時・投稿枠の管理
- 投稿予定と投稿履歴のYAML管理
- 投稿結果・エラーの書き戻し
- AIとの会話による投稿追加・修正・履歴検索

X、Instagram、Facebook、Bluesky、TikTokなどには対応していません。

## AI操作環境

### ChatGPT／Codex

`AGENTS.md`の共通ルールに従って、投稿予定・履歴を管理します。

### 通常のClaudeチャット＋GitHub MCP

Claudeチャットへ公式GitHub MCPコネクタを接続し、対象リポジトリへ必要な書き込み権限を付与すると、同じYAML投稿台帳を作成・更新できます。

- リポジトリとファイルの読み取り
- YAMLなどのファイル作成・更新
- コード検索
- Issue・Pull Request操作
- GitHub Actionsの確認・操作

Claudeチャットでは、最初に`CLAUDE.md`と`AGENTS.md`を読ませてから作業を依頼します。

権限が読み取り専用になっている場合は編集できません。リポジトリ全体へ過剰な権限を与えず、対象リポジトリへ必要最小限の権限だけを付与してください。

### Claude Code

`CLAUDE.md`から`AGENTS.md`の共通ルールを参照し、同じ投稿台帳を管理します。

ClaudeチャットとClaude Codeは別々の操作環境として検証します。投稿追加、日時変更、キャンセル、履歴検索、重複確認、画像・ツリー投稿の作成を確認後、正式な対応環境へ追加します。

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
docs/                    データ形式・利用手順・安全方針
AGENTS.md                 AI共通の作業ルール
CLAUDE.md                 Claudeチャット／Claude Code用の入口と追加ルール
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

Secretsの実値を、コード、YAML、Issue、AIとの会話、メールへ保存しないでください。

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
5. 利用するAI環境とGitHubを接続する
6. `Test Threads Connection`を実行する
7. dry runで投稿予定を確認する
8. 少数のテスト投稿で動作確認する
9. 利用するAIに応じて`AGENTS.md`または`CLAUDE.md`を確認する

## 投稿データ

投稿形式は`docs/POST_SCHEMA.md`を参照してください。

投稿対象は、原則として以下をすべて満たす項目です。

- 当日の日付と投稿枠が一致
- `status: ready`
- `threads_post_id`が空

投稿成功後は`status: posted`、投稿ID、投稿日時を自動記録します。

`ready`へ変更した時点で自動投稿対象になるため、投稿時刻が到来済み、または30分以内の場合は、AIが勝手に`ready`へ変更しないルールにしています。

## 操作例

- ChatGPT／Codex：`docs/CHATGPT_USAGE.md`
- 通常のClaudeチャット：`docs/CLAUDE_CHAT_USAGE.md`
- Claude Code：`docs/CLAUDE_CODE_USAGE.md`

## 安全方針

- パスワードやトークンを運営者またはAIへ渡さない
- 利用者本人がSecretsへ入力する
- 投稿管理リポジトリはPrivateにする
- AIのGitHub権限は対象リポジトリへ限定する
- 読み取りだけでよい作業では書き込み権限を付与しない
- Public画像リポジトリへ投稿本文・履歴・顧客情報を置かない
- 画像は利用権利を持つものだけを使用する
- 投稿済みIDと履歴をAIに変更させない
- 契約終了時は運営者権限・AI連携権限・画像用トークンを失効する

## 現在の未検証項目

- 新規顧客アカウントへの導入リハーサル
- Threads API認証エラー時の全パターン
- ツリー途中失敗後の復旧
- GitHub Actionsの重複実行耐性
- Public画像URLの長期運用
- 10分間隔の投稿時刻判定
- 通常のClaudeチャット＋GitHub MCPからの投稿追加・変更・履歴検索
- Claude Codeからの投稿追加・変更・履歴検索
- ChatGPT／Codex、Claudeチャット、Claude Codeで同じ結果になるかの比較

販売前チェックが完了するまで、本リポジトリを完成品として配布しません。
