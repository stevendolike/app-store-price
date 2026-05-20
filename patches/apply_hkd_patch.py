#!/usr/bin/env python3
"""
apply_hkd_patch.py
將 app-store-price 項目嘅基準貨幣由 CNY 改為 HKD。
所有 patch 均為 idempotent（可重複執行）。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
ERRORS = []


# ── 1. ExchangeRateUtil.java ──────────────────────────────────────────────────
def patch_eu(path: Path):
    label = "ExchangeRateUtil.java: add convertToHkd()"
    if not path.exists():
        ERRORS.append(f"[SKIP] {label}: 檔案不存在")
        return

    text = path.read_text(encoding="utf-8")

    if "convertToHkd" in text:
        print(f"[SKIP] {label}: 已存在，跳過")
        return

    sig = "convertToCny"
    sig_pos = text.find(sig)
    if sig_pos == -1:
        ERRORS.append(f"[WARN] {label}: 找不到 convertToCny")
        return

    print(f"[DEBUG] convertToCny 附近: {repr(text[max(0,sig_pos-30):sig_pos+100])}")

    brace_open = text.find("{", sig_pos)
    if brace_open == -1:
        ERRORS.append(f"[WARN] {label}: 找不到方法 {{")
        return

    depth, brace_close = 0, -1
    for i in range(brace_open, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                brace_close = i
                break

    if brace_close == -1:
        ERRORS.append(f"[WARN] {label}: 找不到方法結束 }}")
        return

    method_start = text.rfind("\n", 0, sig_pos) + 1
    cny_method = text[method_start:brace_close + 1]
    print(f"[DEBUG] 複製方法: {repr(cny_method[:80])}")

    hkd_method = (
        cny_method
        .replace("convertToCny", "convertToHkd")
        .replace("AreaEnum.CHINA", "AreaEnum.HONGKONG")
    )

    insert_pos = brace_close + 1
    new_text = (
        text[:insert_pos]
        + "\n\n    /**\n     * convert to hkd\n     */\n    "
        + hkd_method.lstrip()
        + text[insert_pos:]
    )
    path.write_text(new_text, encoding="utf-8")
    print(f"[OK]   {label}: 替換成功")


patch_eu(ROOT / "src/main/java/com/hypo/appstoreprice/common/ExchangeRateUtil.java")


# ── 2. Money.java ─────────────────────────────────────────────────────────────
def patch_money(path: Path):
    label = "Money.java"
    if not path.exists():
        ERRORS.append(f"[SKIP] {label}: 檔案不存在")
        return

    text = path.read_text(encoding="utf-8")
    changed = False

    # 加 hkdPrice 欄位（只在未存在時）
    if "hkdPrice" not in text:
        old = '    private BigDecimal cnyPrice;\n'
        new = '    private BigDecimal cnyPrice;\n\n    /**\n     * hkd price\n     */\n    private BigDecimal hkdPrice;\n'
        if old in text:
            text = text.replace(old, new, 1)
            changed = True
            print(f"[OK]   {label}: hkdPrice 欄位已加入")
        else:
            ERRORS.append(f"[WARN] {label}: 找不到 cnyPrice 欄位")
    else:
        print(f"[SKIP] {label}: hkdPrice 欄位已存在")

    # 加 convertToHkd 呼叫（只在未存在時）
    if "convertToHkd" not in text:
        old = '        this.cnyPrice = ExchangeRateUtil.convertToCny(price, currencyCode);\n    }'
        new = '        this.cnyPrice = ExchangeRateUtil.convertToCny(price, currencyCode);\n        this.hkdPrice = ExchangeRateUtil.convertToHkd(price, currencyCode);\n    }'
        if old in text:
            text = text.replace(old, new, 1)
            changed = True
            print(f"[OK]   {label}: convertToHkd 呼叫已加入")
        else:
            ERRORS.append(f"[WARN] {label}: 找不到 constructor 目標字串")
    else:
        print(f"[SKIP] {label}: convertToHkd 呼叫已存在")

    if changed:
        path.write_text(text, encoding="utf-8")


patch_money(ROOT / "src/main/java/com/hypo/appstoreprice/pojo/bean/Money.java")


# ── 3. AppService.java ────────────────────────────────────────────────────────
def patch_simple(path: Path, replacements: list, label: str):
    if not path.exists():
        ERRORS.append(f"[SKIP] {label}: 檔案不存在")
        return
    text = path.read_text(encoding="utf-8")
    changed = False
    for old, new in replacements:
        if old in text:
            text = text.replace(old, new)
            changed = True
            print(f"[OK]   {label}: 替換成功")
        elif new in text:
            print(f"[SKIP] {label}: 已存在，跳過")
        else:
            ERRORS.append(f"[WARN] {label}: 找不到目標字串\n       目標: {repr(old[:80])}")
    if changed:
        path.write_text(text, encoding="utf-8")


patch_simple(
    ROOT / "src/main/java/com/hypo/appstoreprice/service/AppService.java",
    [
        (
            '.sorted(Comparator.comparing(item -> item.getPrice().getCnyPrice()))',
            '.sorted(Comparator.comparing(item -> item.getPrice().getHkdPrice()))',
        ),
        (
            '.sorted(Comparator.comparing(Money::getCnyPrice))',
            '.sorted(Comparator.comparing(Money::getHkdPrice))',
        ),
    ],
    "AppService.java: sort by HKD",
)


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
        print("[SKIP] index.html: 無變化")
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
