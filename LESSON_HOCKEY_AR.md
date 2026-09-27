# درس: إضافة موقع جديد خطوة بخطوة

الموقع: https://www.scrapethissite.com/pages/forms/
موقع مخصص للتدريب على السكرابينغ، فيه جدول لـ 582 فريق هوكي (من 1990 إلى 2011) موزع على عدة صفحات، مع خانة بحث.

## الخطوة 1: افتح الموقع وانظر إلى البيانات
جدول بأعمدة: Team Name, Year, Wins, Losses, OT Losses, Win %, GF, GA, +/-
وفي الأسفل أرقام صفحات وزر ».

## الخطوة 2: اكتشف المحددات (Inspect)
اضغط بالزر الأيمن على اسم فريق ← **Inspect**. سترى:

```html
<tr class="team">
  <td class="name">   Boston Bruins </td>
  <td class="year">   1990 </td>
  <td class="wins">   44 </td>
  ...
</tr>
```

إذن:
- كل فريق = سطر `tr.team`
- كل خانة لها class خاص: `name`, `year`, `wins`, `losses`, `ot-losses`, `pct`, `gf`, `ga`, `diff`

اضغط بالزر الأيمن على زر » ← Inspect:
```html
<a href="/pages/forms/?page_num=2&per_page=25" aria-label="Next">
```
إذن الصفحة التالية = `a[aria-label="Next"]`

## الخطوة 3: جرّب البحث
اكتب `new` في خانة البحث واضغط Search. لاحظ الرابط في الأعلى:
```
?page_num=1&per_page=25&q=new
```
البحث مجرد باراميتر في الرابط (`q=`). لا نحتاج ملء نموذج؛ نبني الرابط مباشرة.
وجرّب تغيير `per_page=25` إلى `per_page=100` يدوياً في الرابط: الموقع يقبل، فنحتاج 6 صفحات بدل 24 (طلبات أقل = أسرع وأكثر أدباً).

## الخطوة 4: اكتب الملف `scrapekit/sites/hockey.py`
الفكرة كلها في دالة واحدة:
```python
for tr in soup.select("tr.team"):                          # كل سطر
    cell = lambda cls: tr.select_one(f"td.{cls}").get_text(strip=True)
    rows.append({"team": cell("name"), "year": int(cell("year")), ...})
nxt = soup.select_one('a[aria-label="Next"]')              # الصفحة التالية
```
ملاحظة مهمة: عمود `OT Losses` فارغ في السنوات القديمة. لو كتبنا `int("")` لانهار البرنامج، لذلك دالة `_int` ترجع `None` للخانة الفارغة. هذا النوع من التفاصيل هو ما يفرّق سكرابر يعمل عن سكرابر ينهار في الصفحة 7.

## الخطوة 5: قواعد التحقق (validate.py)
```python
HOCKEY_RULES = [team مطلوب, year بين 1900 و2100, wins بين 0 و100, win_pct بين 0 و1 ...]
```
المفتاح الفريد = (team, year): نفس الفريق يظهر في عدة سنوات، لكن لا يتكرر في نفس السنة.

## الخطوة 6: شغّل
```
python -m scrapekit hockey
python -m scrapekit hockey --query boston
python -m pytest tests -q
```
المتوقع: 582 سطر، duplicates: 0، RESULT: PASS، في 6 طلبات فقط. والاختبارات 27 passed.

## الخلاصة: كم استغرق موقع جديد؟
- اكتشاف المحددات: 5 دقائق
- كتابة الملف: 30 سطراً
- التحقق والاختبارات: 15 دقيقة
كل ما تبقى (التحميل، الكاش، حد السرعة، التحقق، التصدير) جاهز ولم نلمسه.

## تمرين لك
في نفس الموقع صفحة: https://www.scrapethissite.com/pages/simple/
(250 دولة: الاسم، العاصمة، السكان، المساحة).
افتح Inspect واكتشف المحددات بنفسك، ثم اكتب `sites/countries.py` على نمط `hockey.py`. أرسله لي وسأراجعه.
