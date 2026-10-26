# YamRail/Code_CLI

専門家・技術調査担当者が、出典を確認してから調査・実装へ進むための可搬CLIです。
既設Ingridge WorkLedgerとIntent Guardを使い、命令、試行、証憑、停止・復元を記録します。
正本昇格・公開・外部提出を実行する製品権限はありません。

## 最初の操作

Python 3.11以上でcoreを利用できます。A4のGraphと報告書を含むオフライン一式は、
CPython 3.12 x64と同梱のOSS wheelhouseを使います。

```powershell
python yr_code.py doctor --format json
python yr_code.py evidence verify --manifest MANIFEST.json
python install.py
.\yr-code.cmd demo
.\yr-code.cmd recon local --root fixtures/safe_public_or_synthetic
.\yr-code.cmd graph render --input fixtures/osint_case.json --type content --paper a4-landscape --out out/graph
.\yr-code.cmd report make --input fixtures/osint_case.json --paper a4-landscape --out out/report
.\yr-code.cmd status --format json
```

Linuxでは `python3` と `./yr-code.sh` を使用します。初回の外部API呼出しやPrivate GitHub
認証は不要です。実行ごとに新しい作業ディレクトリを作り、既存結果を自動再実行しません。

## 実証範囲

共有3回・4回目拒否・別名拒否、実プロセスの停止とUNKNOWN保持、別目的の継続、SHA改変検知を
合成Fixtureで実行します。Coding Agentの元のprivate台帳は同梱せず、由来を示した安全な
コードFixtureを現在のnative工程内で試験します。新しいモデル生成やCodex内部制御の実証ではありません。

ローカル調査は同梱の合成対象を読み、ハッシュと静的所見を出します。能動走査、脆弱性悪用、
認証突破や対象変更は行いません。Graphは指定固定版のYamRail/OSINT系を転用し、
A4横297×210mmのSVG/PNG/PDF、Graph Master、出典と原MDの結合、receiptを保存します。
参照関係から因果関係を補いません。

## 残るHOLD

Nightshift/NemotronとZetarisの実接続は未実行です。Meterless World Modelのローカル実行は
Nodeが必要です。RAM、暗号化、残留情報消去、Agent全体の物理隔離を保証していません。

AutoCADは既定OFFです。端末内の有効な製品利用権と対話ユーザーブローカーを実証できるまで
起動しません。実装はローカルの照査・拒否経路が中心で、ライセンス付き実接続は未検証です。
サーバー・Cloud・遠隔Agentによる操作や代替起動は常に禁止します。

工具棚の件数は搭載・導入済み工具数ではありません。出自、ライセンス、成熟度、実行状態、
移管可否を別々に記録しています。権利不明な既設素材は索引に保持し、提出用ソースから除外します。

## 引継ぎ

`work_handover --run .yr-code/runs/<対象>` で読込済みnative証憑に結び付く引継ぎ票を作ります。
native台帳は作成場所に結合します。別端末へ移した台帳を黙って再結合せず、原証憑のハッシュを
参照した新しい作業命令で続けます。原失敗・UNKNOWN・HOLDを消してはいけません。

導入・撤去は [INSTALL.md](INSTALL.md)、権限境界は [AGENT_BOUNDARY.md](AGENT_BOUNDARY.md)、
安全範囲は [SAFETY_AND_SCOPE.md](SAFETY_AND_SCOPE.md) に記載しています。
外部提出、公開、Private sourceの開示、新規有料API、正本昇格は別Human Gateです。
