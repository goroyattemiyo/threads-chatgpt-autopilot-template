# Threads Chat Autopilot Template

ChatGPTまたはClaudeの通常チャットから投稿予定を管理し、GitHub ActionsとThreads APIで自動投稿するための汎用テンプレートです。

> 現在は **v0.1・販売前検証中** です。通常チャットからの実動テストが完了するまで、本番向け完成品としては扱いません。

## 対応範囲

現時点の対応SNSは **Threadsのみ** です。

- テキスト投稿
- 画像付き投稿
- ツリー形式の投稿
- 投稿日時・投稿枠の管理
- 投稿予定と投稿履歴のYAML管理
- 投稿結果・エラーの書き戻し
- 投稿履歴検索
- 類似投稿検索
- エラー分類・機密値マスク・復旧Artifact
- 画像リポジトリ設定・アクセスの事前検査
- AIチャットとの会話による投稿追加・修正・履歴検索

X、Instagram、Facebook、Bluesky、TikTokなどには対応していません。

## AI操作環境

### 最優先：ChatGPTチャット

GitHub連携を利用し、`AGENTS.md`の共通ルールに従って投稿予定・履歴を管理します。

### 最優先：通常のClaudeチャット＋GitHub MCP

公式GitHub MCPコネクタを接続し、対象リポジトリへ必要な書き込み権限を付与すると、同じYAML投稿台帳を作成・更新できます。

Claudeチャットでは、最初に`CLAUDE.md`と`AGENTS.md`を読ませます。

権限が読み取り専用の場合は編集できません。書き込み対象は、この投稿管理リポジトリへ限定してください。

### 後回し：Codex／Claude Code

CodexとClaude Codeは、PythonやGitHub Actionsの修正、大規模変更、高度な技術調査向けです。

初期モニターの日常的な投稿管理では、通常チャットを標準とし、CodexやClaude Codeを前提にしません。

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
CLAUDE.md                 Claudeチャット／Claude Code用ルール
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

本処理では、Public画像リポジトリをcheckoutする前に、トークン登録、`owner/repository`形式、ブランチ形式、GitHub APIでのアクセス可否を検査します。失敗時は画像変換・画像削除・投稿YAML更新を開始しません。

## 初期設定

1. `TEMPLATE_SETUP.md`を読む
2. `config/service.yml`を顧客環境へ合わせる
3. 利用者本人がGitHub Secretsを登録する
4. 画像投稿時はPublic画像リポジトリとVariablesを設定する
5. ChatGPTまたはClaudeの通常チャットとGitHubを接続する
6. `Test Threads Connection`を実行する
7. dry runで投稿予定を確認する
8. 少数のテスト投稿で動作確認する
9. 利用するチャットに応じて`AGENTS.md`または`CLAUDE.md`を確認する

## 投稿データ

投稿形式は`docs/POST_SCHEMA.md`を参照してください。

投稿対象は、原則として以下をすべて満たす項目です。

- 当日の日付と投稿枠が一致
- `status: ready`
- `threads_post_id`が空

投稿成功後は`status: posted`、投稿ID、投稿日時を自動記録します。

`ready`へ変更した時点で自動投稿対象になるため、投稿時刻が到来済み、または30分以内の場合は、AIが勝手に`ready`へ変更しないルールにしています。

## 投稿履歴検索

`posts/posted_log.yml`を、本文、投稿ID、期間、カテゴリ、画像有無、ツリー有無、ルート／返信で検索できます。

```bash
python -m src.search_posts history --query "キャンペーン"
python -m src.search_posts history --date-from 2026-07-01 --date-to 2026-07-31
python -m src.search_posts history --category campaign
python -m src.search_posts history --has-image yes
python -m src.search_posts history --thread yes --role reply
```

## 類似投稿検索

`posts/schedules/*.yml`にあるルート本文と返信本文から、類似候補を検索できます。

```bash
python -m src.search_posts similar \
  --text "新しく登録したい投稿本文" \
  --threshold 0.55
```

編集中の投稿自身を除外する場合：

```bash
python -m src.search_posts similar \
  --text "編集後の投稿本文" \
  --threshold 0.55 \
  --exclude-id post-id-to-exclude
```

完全一致は類似度`1.0`です。全角・半角、英字の大小、空白、句読点を正規化します。意味理解による類似判定ではないため、最終判断は本文を目視確認してください。

## エラー復旧

投稿失敗時は、可能な範囲で`error_kind`、`error_code`、`recovery_action`を投稿YAMLへ記録します。Actions失敗時は復旧用Artifactを保存します。

認証情報やトークンをIssue・チャットへ貼らず、`docs/ERROR_RECOVERY.md`の手順に従ってください。Threads上に投稿済みの可能性がある場合は、実画面・Actionsログ・Artifactを照合するまで再実行しません。

画像処理失敗時も、`ASSETS_REPO_TOKEN`の実値をIssue・チャット・メール・ログへ貼りません。`assets_configuration`、`assets_authentication`、`assets_repository_not_found`、`assets_api`の分類とActionsログを確認します。

## 操作例

- ChatGPTチャット：`docs/CHATGPT_USAGE.md`
- 通常のClaudeチャット：`docs/CLAUDE_CHAT_USAGE.md`
- Claude Code：`docs/CLAUDE_CODE_USAGE.md`（後回し）

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
- GitHub Actionsの重複実行耐性
- Public画像URLの長期運用
- 10分間隔の投稿時刻判定
- ChatGPTチャットからの投稿追加・変更・履歴検索
- 通常のClaudeチャット＋GitHub MCPからの投稿追加・変更・履歴検索
- 2つの通常チャットで同じ結果になるかの比較

販売前チェックが完了するまで、本リポジトリを完成品として配布しません。
