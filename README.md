# App Store Price（港幣版）

> 本 repo 係 [hypooo/app-store-price](https://github.com/hypooo/app-store-price) 嘅 fork，加入咗以**港幣（HKD）為基準匯率**嘅修改，適合香港用戶使用。

## 與上游的差異

| 項目 | 上游原版 | 本 fork |
|---|---|---|
| 全球比價基準貨幣 | 人民幣 ¥ | 港幣 HK$ |
| 排序依據 | CNY 換算價 | HKD 換算價 |
| 匯率來源 | ExchangeRate-API | ExchangeRate-API（相同） |

修改涉及以下檔案：
- `src/main/java/com/hypo/appstoreprice/common/ExchangeRateUtil.java` — 新增 `convertToHkd()` 方法
- `src/main/java/com/hypo/appstoreprice/pojo/bean/Money.java` — 新增 `hkdPrice` 欄位
- `src/main/java/com/hypo/appstoreprice/service/AppService.java` — 排序改用 `hkdPrice`
- `src/main/resources/static/index.html` — 介面顯示改為 HK$

## 匯率來源

匯率數據來自 **[ExchangeRate-API](https://www.exchangerate-api.com/)** 免費公開接口：

```
https://open.er-api.com/v6/latest/{貨幣代碼}
```

- 每日更新一次
- 項目內建 Hutool 快取，避免重複請求
- 港幣與美元掛鈎（聯繫匯率制度），匯率極為穩定（約 7.78）
- **注意：匯率換算僅供參考，實際購買價格以 App Store 顯示為準**

## 自動同步機制

本 repo 透過 **GitHub Actions** 每天自動：

1. 同步上游 `hypooo/app-store-price` 最新代碼
2. 應用 HKD patch（`patches/apply_hkd_patch.py`）
3. Build Docker image 並 push 至 GitHub Container Registry (ghcr.io)

排程時間：每天香港時間上午 10:00（UTC 02:00）

如需手動觸發：**Actions → Sync upstream, apply HKD patch & build → Run workflow**

## Docker 部署

```bash
docker run -d \
  --name app-store-price \
  -p 8080:8080 \
  --restart unless-stopped \
  ghcr.io/stevendolike/app-store-price:latest
```

訪問 `http://localhost:8080`

## 更新 image

```bash
docker pull ghcr.io/stevendolike/app-store-price:latest
docker stop app-store-price && docker rm app-store-price
docker run -d \
  --name app-store-price \
  -p 8080:8080 \
  --restart unless-stopped \
  ghcr.io/stevendolike/app-store-price:latest
```

---

原項目功能、安裝說明及技術棧請參閱 [上游 README](https://github.com/hypooo/app-store-price#readme)。
