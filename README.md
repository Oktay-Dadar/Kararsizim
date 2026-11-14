# Kararsizim

## Kullanılan Teknolojiler

Kullanıcıdan veritabanına doğru:

1. **HTML + CSS + Vanilla JS**: Arayüz. Django şablonlarıyla sunucuda üretilir; framework yok.
2. **Vercel (Serverless Python)**: Barındırma ve deployment. Uygulama serverless fonksiyon olarak çalışır.
3. **WhiteNoise**: CSS ve JS gibi statik dosyaları Django'nun kendisinden sunar.
4. **Django 6.1**: Web framework'ü. URL yönlendirme, view'lar, şablonlar, ORM, admin paneli ve testler.
5. **Django Auth + özel User modeli**: Üyelik, giriş ve parola doğrulama.
6. **Python 3.14**: Programlama dili.
7. **python-dotenv**: Yerelde `.env` dosyasındaki ayarları yükler.
8. **dj-database-url**: `DATABASE_URL` metnini Django veritabanı ayarına çevirir.
9. **psycopg 3**: Python ile PostgreSQL arasındaki sürücü.
10. **Supabase (PostgreSQL)**: Veritabanı. Bağlantı transaction pooler üzerinden; Supabase Auth ve RLS kullanılmaz.
11. **SQLite**: Yalnızca yerel geliştirmede, `DATABASE_URL` boşsa devreye girer.

**Geliştirme araçları:** Git + GitHub (sürüm kontrolü), `.venv` (sanal ortam), Django test runner (testler).
