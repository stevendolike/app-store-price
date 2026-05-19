#!/usr/bin/env python3
"""
apply_hkd_patch.py
將 app-store-price 項目嘅基準貨幣由 CNY 改為 HKD。
用字串替換而非 diff patch，對上游代碼更新有更好容錯性。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
ERRORS = []


def patch_file(path: Path, replacements: list[tuple[str, str]], label: str):
    """對檔案做多個字串替換，回報結果。"""
    if not path.exists():
        ERRORS.append(f"[SKIP] {label}: 檔案不存在 {path}")
        return
    text = path.read_text(encoding="utf-8")
    changed = False
    for old, new in replacements:
        if old in text:
            text = text.replace(old, new)
            changed = True
            print(f"[OK]   {label}: 替換成功")
        else:
            # 可能已經 patch 過，檢查 new 是否已存在
            if new in text:
                print(f"[SKIP] {label}: 已經 patch 過，跳過")
            else:
                ERRORS.append(f"[WARN] {label}: 找不到目標字串，請人手確認\n       目標: {repr(old[:80])}")
    if changed:
        path.write_text(text, encoding="utf-8")


# ── 1. ExchangeRateUtil.java ──────────────────────────────────────────────────
eu_path = ROOT / "src/main/java/com/hypo/appstoreprice/common/ExchangeRateUtil.java"

# 喺 convertToCny 方法之後插入 convertToHkd
# 原文：public static BigDecimal convertToCny(...)  { return convertTo(..., "CNY"); }
# 我哋搵 convertToCny 整個方法塊，在其後插入新方法
EU_OLD = '    public static BigDecimal convertToCny(BigDecimal price, String currencyCode) {\n        return convertTo(price, currencyCode, "CNY");\n    }'
EU_NEW = '''    public static BigDecimal convertToCny(BigDecimal price, String currencyCode) {
        return convertTo(price, currencyCode, "CNY");
    }

    /**
     * convert to hkd
     */
    public static BigDecimal convertToHkd(BigDecimal price, String currencyCode) {
        if (price == null || price.compareTo(java.math.BigDecimal.ZERO) == 0) {
            return java.math.BigDecimal.ZERO;
        }
        return convertTo(price, currencyCode, "HKD");
    }'''

patch_file(eu_path, [(EU_OLD, EU_NEW)], "ExchangeRateUtil.java: add convertToHkd()")


# ── 2. Money.java ─────────────────────────────────────────────────────────────
money_path = ROOT / "src/main/java/com/hypo/appstoreprice/pojo/bean/Money.java"

# 加 hkdPrice 欄位（喺 cnyPrice 之後）
MONEY_FIELD_OLD = '    private BigDecimal cnyPrice;\n'
MONEY_FIELD_NEW = '    private BigDecimal cnyPrice;\n\n    /**\n     * hkd price\n     */\n    private BigDecimal hkdPrice;\n'

# 喺 constructor 內加 hkdPrice 賦值（喺 cnyPrice 賦值之後）
MONEY_CTOR_OLD = '        this.cnyPrice = ExchangeRateUtil.convertToCny(price, currencyCode);\n    }'
MONEY_CTOR_NEW = '        this.cnyPrice = ExchangeRateUtil.convertToCny(price, currencyCode);\n        this.hkdPrice = ExchangeRateUtil.convertToHkd(price, currencyCode);\n    }'

patch_file(money_path, [
    (MONEY_FIELD_OLD, MONEY_FIELD_NEW),
    (MONEY_CTOR_OLD, MONEY_CTOR_NEW),
], "Money.java")


# ── 3. AppService.java ────────────────────────────────────────────────────────
svc_path = ROOT / "src/main/java/com/hypo/appstoreprice/service/AppService.java"

patch_file(svc_path, [
    (
        '.sorted(Comparator.comparing(item -> item.getPrice().getCnyPrice()))',
        '.sorted(Comparator.comparing(item -> item.getPrice().getHkdPrice()))',
    ),
    (
        '.sorted(Comparator.comparing(Money::getCnyPrice))',
        '.sorted(Comparator.comparing(Money::getHkdPrice))',
    ),
], "AppService.java: sort by HKD")


# ── 4. index.html ─────────────────────────────────────────────────────────────
html_path = ROOT / "src/main/resources/static/index.html"

if html_path.exists():
    html = html_path.read_text(encoding="utf-8")
    original = html

    # 全球比價 tab：大字顯示 hkdPrice，locale 改 zh-HK
    html = html.replace(
        "formatPrice(price.cnyPrice, 'zh-CN')",
        "formatPrice(price.hkdPrice, 'zh-HK')"
    )
    # 大字前面的 ¥ 符號
    html = html.replace(
        "<span x-show=\"price.price > 0\" class=\"text-xs font-normal opacity-70 mr-0.5\"\n                                                :class=\"{'text-yellow-600 dark:text-yellow-500': index === 0}\">¥</span>",
        "<span x-show=\"price.price > 0\" class=\"text-xs font-normal opacity-70 mr-0.5\"\n                                                :class=\"{'text-yellow-600 dark:text-yellow-500': index === 0}\">HK$</span>"
    )
    # title tooltip 裏面的 ¥
    html = html.replace(
        ":title=\"price.price === 0 ? '免费' : ('¥ ' + formatPrice(price.cnyPrice, 'zh-CN'))\"",
        ":title=\"price.price === 0 ? '免费' : ('HK$ ' + formatPrice(price.hkdPrice, 'zh-HK'))\""
    )

    # 分地區詳情 tab：≈ ¥ 和 cnyPrice
    html = html.replace(
        "formatPrice(app.price.cnyPrice, 'zh-CN')",
        "formatPrice(app.price.hkdPrice, 'zh-HK')"
    )
    html = html.replace(
        "formatPrice(purchase.price.cnyPrice, 'zh-CN')",
        "formatPrice(purchase.price.hkdPrice, 'zh-HK')"
    )
    html = html.replace("≈ ¥<span", "≈ HK$<span")
    html = html.replace(
        "<span\n                                                        class=\"text-xs font-normal text-slate-400 opacity-70 mr-0.5\">¥</span>",
        "<span\n                                                        class=\"text-xs font-normal text-slate-400 opacity-70 mr-0.5\">HK$</span>"
    )

    if html != original:
        html_path.write_text(html, encoding="utf-8")
        print("[OK]   index.html: HKD display patched")
    else:
        print("[SKIP] index.html: 無變化（可能已 patch 或 HTML 結構有變）")
else:
    ERRORS.append("[SKIP] index.html: 檔案不存在")


# ── 結果 ──────────────────────────────────────────────────────────────────────
if ERRORS:
    print("\n⚠️  以下項目需要注意：")
    for e in ERRORS:
        print(e)
    sys.exit(1)
else:
    print("\n✅ 全部 patch 成功！")
