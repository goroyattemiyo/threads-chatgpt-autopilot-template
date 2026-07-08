# 画像リポジトリ設定・接続エラーの復旧

## 最優先ルール

- `ASSETS_REPO_TOKEN`の実値をIssue、チャット、メール、ログへ貼らない
- トークンの入力・更新は利用者本人が行う
- preflight失敗中は画像変換・画像削除・投稿YAML更新を再実行しない
- Public画像リポジトリへ投稿本文、履歴、顧客情報、Secretsを置かない

## エラー分類

### `assets_configuration`

主な原因：

- `ASSETS_REPO_TOKEN`未登録
- `ASSETS_REPO_FULL_NAME`と`assets.repository`が両方空
- リポジトリ名が`owner/repository`形式でない
- ブランチ名の形式不正

復旧：

1. 利用者本人がPrivate自動投稿リポジトリのSettingsを開く
2. Secrets入力前に画面共有を停止する
3. Secret名`ASSETS_REPO_TOKEN`へ画像用Fine-grained PATを登録する
4. Variable名`ASSETS_REPO_FULL_NAME`を`owner/repository`形式で確認する
5. ブランチ名を確認する
6. dry runで画像内容を確認する
7. 本処理を再実行する

## `assets_authentication`

GitHub APIが401または403を返した場合。

確認項目：

- トークンが失効・期限切れではないか
- トークンのRepository accessが画像用リポジトリ1つを含むか
- ContentsがRead and writeか
- リポジトリ所有者がトークン所有者のアクセスを許可しているか

漏えいが疑われる場合は、通常の再試行よりトークン失効・再発行を優先する。

## `assets_repository_not_found`

GitHub APIが404を返した場合。

確認項目：

- 所有者名・リポジトリ名の入力ミス
- リポジトリの削除・改名
- トークンのRepository access対象外
- Privateリポジトリを誤って指定していないか

404は「存在しない」と「トークンから見えない」を区別できない場合があるため、両方を確認する。

## `assets_api`

通信失敗、GitHub API側障害、その他のHTTPエラー。

1. Actionsログのマスク済みエラーを確認する
2. GitHub Statusや一時的障害を確認する
3. 画像、投稿YAML、画像履歴が変更されていないことを確認する
4. 原因が解消してから再実行する

## preflight後の処理順

本処理は次の順番で進む。

1. 画像用設定を確認
2. GitHub APIで画像リポジトリへのアクセスを確認
3. Public画像リポジトリをcheckout
4. 画像をWebPへ変換
5. 投稿YAMLへURLを記録
6. 画像履歴を記録
7. 成功後に元画像を削除
8. Public／Privateリポジトリをcommit

preflight失敗時は3以降へ進まない。
