# テンプレート初期設定

この文書は、顧客ごとのThreads自動投稿リポジトリを作成するときの初期設定手順です。

> 現在はv0.1の構築中です。販売前テストが完了するまでは本番アカウントで使用しないでください。

## 1. 顧客所有のリポジトリを作る

このテンプレートから、顧客本人のGitHubアカウントにPrivateリポジトリを作成します。

推奨名：

```text
threads-autopilot
```

投稿予定、投稿履歴、GitHub Actions、設定はこのPrivateリポジトリで管理します。

## 2. `config/service.yml`を変更する

最低限、以下を顧客環境へ合わせます。

- `service.timezone`
- `threads.account_label`
- `posting.time_slots`
- `posting.enable_images`
- `assets.repository`（画像投稿を利用する場合）

アクセストークンやパスワードは、このファイルへ書かないでください。

## 3. GitHub Secretsを登録する

利用者本人が以下を登録します。

| Secret名 | 用途 |
|---|---|
| `THREADS_ACCESS_TOKEN` | Threads長期アクセストークン |
| `THREADS_USER_ID` | ThreadsユーザーID |
| `ASSETS_REPO_TOKEN` | Public画像リポジトリへの書き込み用。画像投稿を使う場合のみ |

Secretsの値を、運営者、チャット、メール、フォームへ送信しないでください。

## 4. 画像付き投稿を利用する場合

顧客本人のGitHubアカウントに、Public画像リポジトリを作ります。

推奨名：

```text
threads-autopilot-assets
```

Public画像リポジトリへ登録した画像は、インターネット上から閲覧できます。

以下は登録しないでください。

- 個人情報を含む画像
- 機密情報を含む画像
- 公開前に第三者へ見られて困る画像
- 利用権利を持たない画像
- 投稿本文、投稿予定、投稿履歴
- Secretsやトークン

## 5. 画像用Fine-grained Personal Access Token

画像投稿を利用する場合、利用者本人が画像リポジトリだけを対象にしたFine-grained Personal Access Tokenを作成します。

推奨権限：

- Repository access：画像用リポジトリ1つだけ
- Contents：Read and write
- 有効期限：必要な期間のみ

作成した値は、Private自動投稿リポジトリの`ASSETS_REPO_TOKEN`へ登録します。

## 6. 投稿データを登録する

投稿予定は`posts/schedules/`内のYAMLファイルへ登録します。

詳しい形式は`docs/POST_SCHEMA.md`を参照してください。

## 7. テスト順序

1. Threadsプロフィール取得テスト
2. テキスト投稿のdry run
3. 短いテキストのテスト投稿
4. 投稿履歴への記録確認
5. 画像変換のdry run
6. Public画像URLの表示確認
7. 画像付きテスト投稿
8. 2件のツリー投稿テスト
9. 二重投稿防止の確認
10. エラー時のIssue・ログ確認

## 8. 本番開始条件

以下をすべて確認してから本番運用を開始します。

- Secretsがコードやログに表示されない
- dry runが成功する
- テキスト投稿が成功する
- 投稿IDと投稿時刻が履歴に残る
- 画像URLが外部から参照できる
- ツリー投稿の順番が正しい
- 再実行しても二重投稿されない
- 失敗時に`status: error`と原因が記録される
