#!/usr/bin/env python3
"""
apply_hkd_patch.py
將 app-store-price 項目嘅基準貨幣由 CNY 改為 HKD。
用字串/regex 替換，對上游代碼更新有更好容錯性。
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
ERRORS = []


def patch_file(path: Path, replacements: list, label: str):
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
            if new in text:
                print(f"[SKIP] {label}: 已經 patch 過，跳過")
            else:
                ERRORS.append(f"[WARN] {label}: 找不到目標字串，請人手確認\n       目標: {repr(old[:80])}")
    if changed:
        path.write_text(text, encoding="utf-8")


def patch_eu(path: Path):
    """
    用 regex 插入 convertToHkd()，唔理縮排/換行差異。
    搵 convertToCny 方法，喺其後插入新方法。
    """
    label = "ExchangeRateUtil.java: add convertToHkd()"
    if not path.exists():
        ERRORS.append(f"[SKIP] {label}: 檔案不存在 {path}")
        return

    text = path.read_text(encoding="utf-8")

    # 已經 patch 過就跳過
    if "convertToHkd" in text:
        print(f"[SKIP] {label}: 已經 patch 過，跳過")
        return

    # debug：印出 convertToCny 附近內容方便排查
    idx = text.find("convertToCny")
    if idx == -1:
        ERRORS.append(f"[WARN] {label}: 找不到 convertToCny，請人手確認")
        return
    print(f"[DEBUG] convertToCny 附近內容: {repr(text[max(0,idx-30):idx+150])}")

    # regex：匹配 convertToCny 整個方法（容許任意空白/縮排）
    pattern = re.compile(
        r'([ \t]*(?:public\s+)?static\s+BigDecimal\s+convertToCny\s*\([^)]*\)\s*\{[^}]*\})',
        re.DOTALL
    )
    match = pattern.search(text)
    if not match:
        ERRORS.append(f"[WARN] {label}: regex 匹配失敗，請人手確認")
        return

    original_method = match.group(1)
    # 用原方法嘅縮排推斷新方法縮排
    indent = re.match(r'^([ \t]*)', original_method).group(1)

    new_method = (
        f"\n\n{indent}/**\n"
        f"{indent} * convert to hkd\n"
        f"{indent} */\n"
        f"{indent}public static BigDecimal convertToHkd(BigDecimal price, String currencyCode) {{\n"
        f"{indent}    if (price == null || price.compareTo(java.math.BigDecimal.ZERO) == 0) {{\n"
        f"{indent}        return java.math.BigDecimal.ZERO;\n"
        f"{indent}    }}\n"
        f"{indent}    return convertTo(price, currencyCode, \"HKD\");\n"
        f"{indent}}}"
    )

    new_text = text.replace(original_method, original_method + new_method, 1)
    path.write_text(new_text, encoding="utf-8")
    print(f"[OK]   {label}: 替換成功")


# ── 1. ExchangeRateUtil.java ──────────────────────────────────────────────────
eu_path = ROOT / "src/main/java/com/hypo/appstoreprice/common/ExchangeRateUtil.java"
patch_eu(eu_path)


# ── 2. Money.java ─────────────────────────────────────────────────────────────
money_path = ROOT / "src/main/java/com/hypo/appstoreprice/pojo/bean/Money.java"

MONEY_FIELD_OLD = '    private BigDecimal cnyPrice;\n'
MONEY_FIELD_NEW = '    private BigDecimal cnyPrice;\n\n    /**\n     * hkd price\n     */\n    private BigDecimal hkdPrice;\n'

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

    html = html.replace("formatPrice(price.cnyPrice, 'zh-CN')", "formatPrice(price.hkdPrice, 'zh-HK')")
    html = html.replace(
        ":title=\"price.price === 0 ? '免费' : ('¥ ' + formatPrice(price.cnyPrice, 'zh-CN'))\"",
        ":title=\"price.price === 0 ? '免费' : ('HK$ ' + formatPrice(price.hkdPrice, 'zh-HK'))\""
    )
    html = html.replace(">¥</span>", ">HK$</span>")
    html = html.replace("formatPrice(app.price.cnyPrice, 'zh-CN')", "formatPrice(app.price.hkdPrice, 'zh-HK')")
    html = html.replace("formatPrice(purchase.price.cnyPrice, 'zh-CN')", "formatPrice(purchase.price.hkdPrice, 'zh-HK')")
    html = html.replace("≈ ¥<span", "≈ HK$<span")

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
