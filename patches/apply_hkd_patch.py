#!/usr/bin/env python3
"""
apply_hkd_patch.py
將 app-store-price 項目嘅基準貨幣由 CNY 改為 HKD。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
ERRORS = []


def patch_file(path: Path, replacements: list, label: str):
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
                ERRORS.append(f"[WARN] {label}: 找不到目標字串\n       目標: {repr(old[:80])}")
    if changed:
        path.write_text(text, encoding="utf-8")


def patch_eu(path: Path):
    """
    複製 convertToCny 方法 → convertToHkd，
    將 AreaEnum.CHINA 替換為 AreaEnum.HONGKONG。
    唔需要知道方法內部實現，對上游改動容錯性最強。
    """
    label = "ExchangeRateUtil.java: add convertToHkd()"
    if not path.exists():
        ERRORS.append(f"[SKIP] {label}: 檔案不存在 {path}")
        return

    text = path.read_text(encoding="utf-8")

    if "convertToHkd" in text:
        print(f"[SKIP] {label}: 已經 patch 過，跳過")
        return

    # 搵 convertToCny 方法簽名起點
    sig = "convertToCny"
    sig_pos = text.find(sig)
    if sig_pos == -1:
        ERRORS.append(f"[WARN] {label}: 找不到 convertToCny")
        return

    # 向前搵方法真正開始（可能有 public/javadoc）
    # 搵最近一個換行符之後的位置
    method_start = text.rfind("\n", 0, sig_pos) + 1

    # 搵方法開頭的 {
    brace_open = text.find("{", sig_pos)
    if brace_open == -1:
        ERRORS.append(f"[WARN] {label}: 找不到方法 {{")
        return

    # brace counting 搵配對的 }
    depth = 0
    brace_close = -1
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

    # 提取完整方法
    cny_method = text[method_start:brace_close + 1]
    print(f"[DEBUG] 複製方法: {repr(cny_method[:80])}")

    # 複製並替換
    hkd_method = (
        cny_method
        .replace("convertToCny", "convertToHkd")
        .replace("AreaEnum.CHINA", "AreaEnum.HONGKONG")
    )

    # 插入喺原方法之後
    insert_pos = brace_close + 1
    new_text = text[:insert_pos] + "\n\n    /**\n     * convert to hkd\n     */\n    " + hkd_method.lstrip() + text[insert_pos:]
    path.write_text(new_text, encoding="utf-8")
    print(f"[OK]   {label}: 替換成功")


# ── 1. ExchangeRateUtil.java ──────────────────────────────────────────────────
patch_eu(ROOT / "src/main/java/com/hypo/appstoreprice/common/ExchangeRateUtil.java")


# ── 2. Money.java ─────────────────────────────────────────────────────────────
money_path = ROOT / "src/main/java/com/hypo/appstoreprice/pojo/bean/Money.java"
patch_file(money_path, [
    (
        '    private BigDecimal cnyPrice;\n',
        '    private BigDecimal cnyPrice;\n\n    /**\n     * hkd price\n     */\n    private BigDecimal hkdPrice;\n',
    ),
    (
        '        this.cnyPrice = ExchangeRateUtil.convertToCny(price, currencyCode);\n    }',
        '        this.cnyPrice = ExchangeRateUtil.convertToCny(price, currencyCode);\n        this.hkdPrice = ExchangeRateUtil.convertToHkd(price, currencyCode);\n    }',
    ),
], "Money.java")


# ── 3. AppService.java ────────────────────────────────────────────────────────
patch_file(
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
