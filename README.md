# iris-fastapi — Phân tích hoa Iris: SVM phân loại + so sánh 5 mô hình hồi quy

Hệ thống gồm **3 module**: giao diện web, API mô hình (SVM phân loại loài + 5 mô hình hồi quy
dự đoán `petal_width`) và API CSDL (tài khoản, lịch sử dự đoán, kết quả đánh giá, xuất Excel).
Triển khai trực tuyến trên **Render**.

**URL công khai:** https://iris-svm-fastapi-uvo0.onrender.com

## Kiến trúc 3 module

```
                        ┌──────────────────────────────────────┐
   Trình duyệt ───────▶ │ 1. WEB  (web/, cổng 8080)            │  HTML/CSS/JS thuần, Chart.js
                        │    chỉ gọi API qua HTTP (fetch)      │  không nạp mô hình, không mở CSDL
                        └───────┬──────────────────────┬───────┘
                   fetch + JWT  │                      │  fetch + JWT
                                ▼                      ▼
   ┌─────────────────────────────────────┐   ┌─────────────────────────────────────┐
   │ 2. API MÔ HÌNH  (app.py, cổng 8000) │   │ 3. API CSDL  (db_api/, cổng 8001)   │
   │  SVM: /predict /species /metrics    │   │  /auth/register /auth/login  (bcrypt│
   │  Hồi quy: /regression/train (JWT)   │   │   + JWT)                            │
   │   /regression/metrics  /predict     │   │  /predictions  (lịch sử theo user)  │
   │   /regression/arena                 │   │  /model-runs   (bảng đánh giá)      │
   │   /regression/regularization-path   │   │  /export/*.xlsx (openpyxl)          │
   │   /regression/diagnostics           │   │           │                         │
   │  /dataset/summary                   │   │           ▼                         │
   │  svm_model.pkl, regression_*.pkl    │   │ PostgreSQL (DATABASE_URL, Render)   │
   │                                     │   │ hoặc SQLite data/app.db (cục bộ)    │
   └─────────────────────────────────────┘   │   (migration: db_api/migrations/)   │
         xác minh JWT bằng JWT_SECRET chung  └─────────────────────────────────────┘
```

- **Web điều phối lưu CSDL**: web gọi API mô hình để dự đoán/train, rồi gửi kết quả sang API CSDL kèm JWT.
  Hai API không gọi nhau; API mô hình chỉ *xác minh* JWT (cùng `JWT_SECRET`) để khoá `POST /regression/train`.
- **Chạy cục bộ**: 3 tiến trình, 3 cổng (`SERVICE_MODE=split`, do `run.sh`/`run.ps1` bật).
- **Render (gói Free, 1 dịch vụ)**: `uvicorn app:app` ở chế độ gộp (`SERVICE_MODE=single`, mặc định) —
  app.py *mount* API CSDL tại `/db` và thư mục web tại `/`. Mã của từng module vẫn tách riêng.

## Điểm nổi bật (chức năng sáng tạo)

Nhóm **"Điểm nổi bật"** trên thanh bên của giao diện:

- **Phân tích nâng cao** (`#/phan-tich`) — ba biểu đồ, mỗi biểu đồ kèm nhận xét sinh từ số liệu thật:
  **PCA 2D** (150 mẫu, 4 đặc trưng chuẩn hoá bằng StandardScaler, % phương sai của PC1/PC2 ghi ở nhãn trục,
  dữ liệu từ `GET /dataset/pca`), **Confusion Matrix** của SVM trên tập test (từ `GET /metrics`) và
  **phân bố số lượng 3 loài** (từ `/dataset/summary`). Màu cố định: Setosa `#6366F1`, Versicolor `#10B981`,
  Virginica `#F59E0B`.

Các trang khác: **Tổng quan** — khối dự đoán SVM (4 thanh trượt + ô nhập số đồng bộ hai chiều, giới hạn =
min/max thật trong dữ liệu, mặc định 5.8 / 2.7 / 3.7 / 1.2, nút *Dự đoán* gọi `POST /predict`, hiển thị loài,
ảnh, accuracy tập test, 4 giá trị đầu vào và đặc điểm nhận dạng) và bên dưới là thống kê theo loài theo ảnh mẫu
`docs/ui-reference.png` (mọi số tính từ `Iris.csv` qua `/dataset/summary`); **So sánh mô hình** (bảng xếp hạng,
biểu đồ R²/sai số/thời gian, *Train lại*, *Xuất Excel*), **Phân loại SVM** (trang da1 cũ, giữ nguyên chức năng),
**Lịch sử** (lọc ngày/mô hình, phân trang, sửa giá trị thật, xuất Excel), **Đăng nhập / Đăng ký**.

Các endpoint `POST /regression/arena`, `GET /regression/regularization-path` và `GET /regression/diagnostics`
vẫn còn trong API (dùng được qua Swagger `/docs`) nhưng giao diện web không còn gọi tới.

## Chạy trên máy trắng — một dòng lệnh

Yêu cầu duy nhất: đã cài **Git** và **Python 3.10+**.

> ⚠️ Hai dòng dưới đây **không thay thế cho nhau**. Dán dòng bash vào PowerShell sẽ báo lỗi
> `The token '&&' is not a valid statement separator in this version` — Windows PowerShell 5.1
> không hiểu `&&`. Chọn đúng dòng theo cửa sổ bạn đang mở.

**Git Bash** (biểu tượng *Git Bash* trong Start Menu, hoặc chuột phải trong thư mục → *Open Git Bash here*):

```bash
git clone https://github.com/PiscesSix/iris-svm-fastapi.git && cd iris-svm-fastapi && bash run.sh
```

**PowerShell / Terminal của Windows:**

```powershell
git clone https://github.com/PiscesSix/iris-svm-fastapi.git; cd iris-svm-fastapi; powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Script sẽ: tạo `.venv`, chép `.env.example` → `.env` và **tự sinh `JWT_SECRET` + `ADMIN_PASSWORD`** (in mật
khẩu admin ra màn hình), cài `requirements.txt`, chạy `seed.py` (train 5 mô hình hồi quy nếu chưa có + tạo
tài khoản **`demo` / `demo123`** và **`admin`** + lưu lần train đầu vào CSDL), rồi khởi động 3 module và mở
trình duyệt. Chạy ở máy dùng SQLite `data/app.db` (không cần Postgres):

| Module | Địa chỉ |
|--------|---------|
| Giao diện web | http://127.0.0.1:8080/ |
| API mô hình (Swagger) | http://127.0.0.1:8000/docs |
| API CSDL (Swagger) | http://127.0.0.1:8001/docs |

Dừng cả ba bằng `Ctrl+C`. Các chế độ khác của script (`bash run.sh <chế độ>` hoặc `.\run.ps1 <chế độ>`):

| Chế độ | Việc làm |
|--------|----------|
| *(không có)* | 3 module trên 3 cổng |
| `single` | cả 3 module trong một tiến trình ở cổng 8000 (giống Render) |
| `seed` | chỉ chạy `seed.py` |
| `train` | cài `requirements-dev.txt`, train lại SVM (`train.py`) + 5 mô hình hồi quy (`train_regression.py`), vẽ lại hình |
| `test` | cài `requirements-dev.txt` và chạy `pytest` |

Cấu hình nằm trong `.env` (mẫu: `.env.example`): `JWT_SECRET`, `ADMIN_PASSWORD`, `DB_PATH`, cổng, `CORS_ORIGINS`…
`.env` tạo từ trước khi có trang Dữ liệu SQL sẽ thiếu `ADMIN_PASSWORD`: thêm dòng `ADMIN_PASSWORD=<mật khẩu>`
rồi chạy lại. Muốn chạy ở máy nhưng ghi thẳng vào CSDL Render thì đặt `DATABASE_URL=<External Database URL>`.
Không có secret nào được viết cứng trong mã nguồn.

## Kết quả mô hình

**SVM phân loại loài** (số liệu đầy đủ: `metrics.json`, endpoint `/metrics`):

| Chỉ số | Giá trị |
|--------|---------|
| Cấu hình tốt nhất | `kernel=linear`, `C=0.1` (chọn từ 64 cấu hình bằng GridSearchCV) |
| Accuracy tập kiểm tra | 93.33% |
| Cross-validation (5-fold) | 95.33% ± 3.40% |
| Macro F1 | 93.33% |
| Vector hỗ trợ | 56 / 120 mẫu huấn luyện |

**5 mô hình hồi quy** — target `petal_width`, đặc trưng `sepal_length, sepal_width, petal_length` +
one-hot `species` (setosa làm mốc). Mỗi mô hình là `Pipeline` có `StandardScaler`, chia train/test 80/20
cố định (`random_state=42`), tinh chỉnh bằng `GridSearchCV` + `KFold(5)`:

| Mô hình | Lưới tham số |
|---------|--------------|
| LinearRegression | — |
| Polynomial (PolynomialFeatures + LinearRegression) | `degree ∈ {2, 3, 4}` |
| Ridge | `alpha ∈ logspace(-3, 3, 13)` |
| Lasso | `alpha ∈ logspace(-4, 1, 11)` |
| ElasticNet | `alpha ∈ logspace(-4, 1, 11)`, `l1_ratio ∈ {0.1, 0.3, 0.5, 0.7, 0.9}` |

Chỉ số của từng mô hình (R², MAE, MSE, RMSE, CV R² mean ± std, thời gian train, thời gian predict/mẫu,
số hệ số khác 0, tham số tốt nhất) nằm trong `regression_metrics.json`, endpoint `/regression/metrics`
và trang *So sánh mô hình*. Mô hình tốt nhất được chọn theo **CV R²** (không dùng tập test để chọn).

## Các endpoint

**API mô hình** (`app.py`, cổng 8000; trên Render: gốc của URL):

| Method | Đường dẫn | Chức năng |
|--------|-----------|-----------|
| GET | `/` | Giao diện web (chế độ gộp) hoặc chuyển hướng sang module web (chế độ tách) |
| GET | `/health` | Trạng thái dịch vụ (Render dùng làm health check) |
| GET | `/species` | Thông tin 3 loài hoa kèm ảnh, tác giả, giấy phép, link nguồn |
| GET | `/metrics` | Số liệu đánh giá của SVM |
| POST | `/predict` | Dự đoán loài hoa từ 4 kích thước (SVM) |
| GET | `/dataset/summary` | Thống kê theo loài tính từ `Iris.csv` (trang Tổng quan) |
| GET | `/dataset/pca` | PCA 2D của 150 mẫu đã chuẩn hoá (trang Phân tích nâng cao) |
| GET | `/regression/metrics` | Bảng so sánh 5 mô hình hồi quy |
| POST | `/regression/train` | Train lại 5 mô hình — **cần JWT** |
| POST | `/regression/predict` | Dự đoán `petal_width` bằng 1 mô hình, kèm thời gian chạy |
| POST | `/regression/arena` | Cả 5 mô hình + giá trị đồng thuận + mô hình lệch nhất |
| GET | `/regression/regularization-path?model=` | Hệ số theo α (ridge / lasso / elasticnet) |
| GET | `/regression/diagnostics?model=` | Actual, predicted, residual trên tập test |
| GET | `/docs` | Swagger UI |

**API CSDL** (`db_api/`, cổng 8001; trên Render: tiền tố `/db`):

| Method | Đường dẫn | Chức năng |
|--------|-----------|-----------|
| GET | `/health` | Trạng thái + các migration đã áp dụng |
| POST | `/auth/register` | Đăng ký (mật khẩu băm bcrypt), trả JWT |
| POST | `/auth/login` | Đăng nhập, trả JWT |
| GET | `/auth/me` | Thông tin tài khoản — cần JWT |
| POST | `/predictions` | Lưu 1–20 dự đoán của user hiện tại — cần JWT |
| GET | `/predictions?page=&page_size=&model=&date_from=&date_to=` | Lịch sử **của chính user**, lọc + phân trang — cần JWT |
| PATCH | `/predictions/{id}` | Ghi giá trị thật cho 1 dự đoán của mình — cần JWT |
| POST | `/model-runs` | Lưu bảng đánh giá 5 mô hình của một lần train — cần JWT |
| GET | `/model-runs?limit=` | Các lần train gần nhất |
| GET | `/export/predictions.xlsx?model=&date_from=&date_to=` | Xuất lịch sử ra Excel — cần JWT |
| GET | `/export/model-runs.xlsx?run_id=` | Xuất bảng so sánh mô hình ra Excel — cần JWT |
| GET | `/sql/tables` | Các bảng + số dòng — **chỉ tài khoản admin** |
| GET | `/sql/tables/{name}?limit=&offset=` | Dữ liệu một bảng (username thay cho user_id, không có password_hash) — admin |
| POST | `/sql/query` | Chạy 1 câu SELECT/WITH chỉ đọc, tối đa 500 dòng, 5 giây — admin |

Bảng CSDL (`db_api/migrations/001_initial.sql`): `users`, `predictions` (user_id, created_at, task, model,
input_json, predicted_value/label, actual_value, runtime_ms, batch_id), `training_runs`, `model_runs`,
và `schema_migrations`. Thay đổi schema → thêm tệp `002_*.sql`, không sửa tệp cũ (thêm cả bản PostgreSQL
trong `db_api/migrations/postgres/`).

**Hai backend, cùng một mã:** không đặt `DATABASE_URL` thì dùng SQLite `data/app.db` (chạy cục bộ, pytest);
đặt `DATABASE_URL=postgresql://...` thì dùng PostgreSQL (Render Postgres). `db_api/db.py` bọc psycopg để các
router giữ nguyên câu SQL, dùng pool kết nối (`DB_POOL_SIZE`, mặc định 5). Mỗi lần bấm **Lưu** trên web là một
`INSERT ... COMMIT` ngay, nên dữ liệu thấy được trong SQL tức thì.

File Excel: header in đậm nền tím, cột tự giãn, mỗi loại dữ liệu một sheet, tên file có dấu thời gian
(`lich_su_du_doan_YYYYMMDD_HHMMSS.xlsx`, `so_sanh_mo_hinh_YYYYMMDD_HHMMSS.xlsx`).

```bash
curl -X POST "https://iris-svm-fastapi-uvo0.onrender.com/predict" \
  -H "Content-Type: application/json" \
  -d '{"sepal_length":5.1,"sepal_width":3.5,"petal_length":1.4,"petal_width":0.2}'
```

## Kiểm thử

```bash
bash run.sh test          # hoặc: .venv/Scripts/python -m pytest
```

`tests/` kiểm tra đăng ký/đăng nhập (bcrypt, JWT, 401/409/422), dự đoán SVM (contract cũ không đổi) và
hồi quy, đấu trường, badge tốc độ, lưu lịch sử + cô lập theo user, bảng `model_runs`, và 2 file Excel.
Test chạy trên CSDL SQLite tạm, không đụng `data/app.db` hay mô hình đã commit. Chạy cùng bộ test trên
PostgreSQL: đặt `TEST_DATABASE_URL=postgresql://...` trỏ tới một CSDL **trống** (không bao giờ dùng CSDL thật;
`DATABASE_URL` trong `.env` bị bỏ qua khi chạy test).

## Triển khai lên Render — hướng dẫn từ đầu

Phần này dành cho người vừa pull code về và muốn có **bản chạy online của riêng mình**: web + API trên một
Web Service, dữ liệu (tài khoản, lịch sử dự đoán, các lần train) lưu trong **Render Postgres**. Mọi thứ đều ở
gói **Free**, không cần thẻ thanh toán.

### Bước 0 — Chuẩn bị

1. **Code trên GitHub của bạn.** Render chỉ build từ repo mà tài khoản của bạn truy cập được:
   - Cách nhanh: mở https://github.com/PiscesSix/iris-svm-fastapi → **Fork**.
   - Hoặc đẩy bản đã clone lên một repo mới (tạo repo trống `iris-svm-fastapi` trên GitHub trước):

     ```powershell
     git clone https://github.com/PiscesSix/iris-svm-fastapi.git
     cd iris-svm-fastapi
     git remote set-url origin https://github.com/<tai-khoan-cua-ban>/iris-svm-fastapi.git
     git push -u origin main
     ```
2. **Tài khoản Render**: đăng ký tại https://render.com bằng GitHub (cho phép Render đọc repo ở bước trên).
3. Mỗi workspace Render chỉ có **1 CSDL Postgres Free**. Nếu đã có một cái, xoá nó hoặc dùng workspace khác.
4. Hai tệp mô hình `svm_model.pkl` và `regression_models.pkl` **phải có trong repo** (đã commit sẵn; đừng
   thêm chúng vào `.gitignore`), nếu không app chết lúc khởi động với `FileNotFoundError`.

### Cách A — Blueprint (khuyến nghị: Render tự tạo CSDL và tự điền biến môi trường)

`render.yaml` trong repo đã khai báo đủ: Web Service `iris-svm-fastapi` + Postgres `iris-svm-db` (cả hai Free)
và 4 biến môi trường. Bạn không phải copy chuỗi kết nối hay mật khẩu nào.

1. Render → **New +** → **Blueprint** → chọn repo của bạn → **Connect**.
2. **Blueprint Name**: `iris-svm-fastapi`; **Branch**: `main`; Blueprint Path để trống (mặc định `render.yaml`).
3. Xem danh sách Render sẽ làm, phải có đủ:
   - Create web service `iris-svm-fastapi` và Create database `iris-svm-db` (Free);
   - biến `SERVICE_MODE`, `JWT_SECRET`, `ADMIN_PASSWORD`, `DATABASE_URL`.

   Nếu workspace đã có service/CSDL trùng tên, Render hỏi thêm: chọn **Associate existing services** để dùng lại.
4. Bấm **Deploy Blueprint**. Render tạo CSDL (~1–2 phút) rồi build web (~2–4 phút) cho tới khi service **Live**.
5. Mở service → lấy URL dạng `https://iris-svm-fastapi-xxxx.onrender.com` (Render thêm hậu tố nếu tên đã có người dùng).

Từ đó, mỗi lần `git push` lên `main`, Render tự deploy lại và áp dụng thay đổi trong `render.yaml`.

### Cách B — Tạo tay (khi không dùng Blueprint)

1. **Tạo CSDL**: Render → **New +** → **Postgres**
   - Name `iris-svm-db`, Database `iris_svm`, User `iris_svm`, **Region**: chọn một vùng (ví dụ Oregon) và
     dùng **đúng vùng đó** cho web service ở bước 2.
   - Mục **Compute** chọn gói **$0 / month (Free)**. Form mặc định chọn gói trả phí, nên phải chọn lại và kiểm
     tra dòng **Total = $0 / month** trước khi bấm **Create Database**.
   - Chờ trạng thái **Available** → bấm **Connect** → tab **Internal** → copy **Internal Database URL**.
2. **Tạo Web Service**: **New +** → **Web Service** → chọn repo, rồi điền:

   | Ô | Giá trị |
   |---|---|
   | Runtime | Python 3 |
   | Region | trùng với CSDL |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `uvicorn app:app --host 0.0.0.0 --port $PORT` |
   | Health Check Path | `/health` |
   | Instance Type | Free |

3. **Environment Variables** (Add Environment Variable) — xem bảng ở mục dưới. Với `JWT_SECRET` và
   `ADMIN_PASSWORD` bấm **Generate** để Render tự sinh; `DATABASE_URL` dán Internal Database URL ở bước 1.
4. **Create Web Service**, chờ **Live**.

### Các biến môi trường

| Biến | Bắt buộc | Giá trị trên Render | Ý nghĩa |
|---|---|---|---|
| `SERVICE_MODE` | có | `single` | chạy 3 module (API mô hình, API CSDL ở `/db`, web ở `/`) trong một tiến trình |
| `JWT_SECRET` | có | Generate | khoá ký token đăng nhập. Thiếu → người dùng bị đăng xuất mỗi lần service khởi động lại |
| `DATABASE_URL` | có | Internal Database URL (Blueprint: tự điền) | có → lưu vào PostgreSQL; **thiếu → dùng SQLite trên ổ đĩa tạm, dữ liệu mất mỗi lần deploy/ngủ dậy** |
| `ADMIN_PASSWORD` | nên có | Generate | mật khẩu tài khoản `admin`, tài khoản duy nhất vào được trang **Dữ liệu SQL**. Thiếu → trang bị khoá |
| `SQL_VIEWER_USERS` | không | mặc định `admin` | danh sách tài khoản được vào trang Dữ liệu SQL (phân cách bằng dấu phẩy) |
| `APP_TZ_OFFSET_HOURS` | không | mặc định `7` | múi giờ cho bộ lọc ngày và thời gian trong file Excel |
| `DB_POOL_SIZE` | không | mặc định `5` | số kết nối tối đa tới PostgreSQL |

Không có biến nào phải chép vào mã nguồn; chạy ở máy thì các biến này nằm trong `.env` (mẫu: `.env.example`).

### Lần khởi động đầu tiên làm gì

App tự tạo bảng (migration `db_api/migrations/postgres/001_initial.sql`), rồi `seed.py` tạo:
tài khoản **`demo` / `demo123`** (công khai, để thử), tài khoản **`admin`** (mật khẩu = `ADMIN_PASSWORD`) và lần
train đầu của 5 mô hình hồi quy. Chạy lại bao nhiêu lần cũng không tạo trùng; đổi `ADMIN_PASSWORD` thì lần khởi
động sau mật khẩu admin được đặt lại theo giá trị mới.

### Kiểm tra sau khi deploy

| Mở | Kết quả đúng |
|---|---|
| `https://<url>/health` | `"status": "healthy"` |
| `https://<url>/db/health` | `"database": "postgresql/iris_svm"` (nếu thấy `app.db` là **chưa nối CSDL**) |
| `https://<url>/docs` | Swagger, có nhóm "Mô hình tuyến tính" |
| `https://<url>/` | giao diện web; đăng nhập `demo` / `demo123` → Phân loại SVM → Dự đoán → **Lưu** |
| trang **Dữ liệu SQL** | đăng nhập `admin` → thấy dòng vừa lưu ở bảng `predictions` |

Gói Free **ngủ sau ~15 phút** không có request; request đầu tiên sau đó mất 30–60 giây. Trước khi demo nên mở
trang trước 2–3 phút. Dữ liệu vẫn còn sau khi ngủ dậy vì nằm trong Postgres.

### Xem dữ liệu

**Lấy mật khẩu admin:** Render → service → **Environment** → dòng `ADMIN_PASSWORD` → bấm biểu tượng con mắt.

**Cách 1 — trên web, trang "Dữ liệu SQL"** (`#/du-lieu-sql`, đăng nhập `admin`): các bảng kèm số dòng, dữ liệu
từng bảng (bật **Tự làm mới mỗi 5 giây** để thấy dòng mới ngay khi có người bấm Lưu), ô chạy câu SQL chỉ đọc
với 4 câu mẫu. Tài khoản `demo` công khai **không** vào được.

Bảo mật của trang này:
- Phân quyền theo `SQL_VIEWER_USERS` (mặc định `admin`); tên này không đăng ký được từ web,
  `seed.py` tạo nó (hoặc đặt lại mật khẩu) theo `ADMIN_PASSWORD`. Không đặt `ADMIN_PASSWORD` = trang bị khoá.
- Chỉ đọc: PostgreSQL chạy câu lệnh trong `SET TRANSACTION READ ONLY` + prepared statement (đúng một câu, nên
  `SELECT 1; COMMIT; DROP ...` bị từ chối), `statement_timeout` 5 giây; SQLite dùng `PRAGMA query_only`.
- Bảng hiển thị `username` thay cho `user_id` và bỏ cột `password_hash`; câu SQL tự gõ không được nhắc tới
  `password_hash`, mọi chuỗi dạng hash bcrypt trong kết quả đều bị che. Tên bảng chỉ nhận tên có thật.
- Mọi giá trị được escape trước khi hiển thị (không XSS). Kiểm thử: `tests/test_sql_explorer.py`.

**Cách 2 — trên máy, `db_viewer.py`** (chỉ đọc). Lấy **External Database URL** ở Render → `iris-svm-db` →
**Connect** → tab **External** (URL này chứa mật khẩu CSDL: không commit, không đưa lên slide). URL lấy từ `--url`,
biến `EXTERNAL_DATABASE_URL` trong `.env`, hoặc được hỏi ẩn khi chạy:

```powershell
.\.venv\Scripts\python.exe db_viewer.py                     # các bảng + số dòng + 10 dự đoán mới nhất
.\.venv\Scripts\python.exe db_viewer.py history --watch 5   # lịch sử, tự làm mới mỗi 5 giây (Ctrl+C thoát)
.\.venv\Scripts\python.exe db_viewer.py history --user demo
.\.venv\Scripts\python.exe db_viewer.py show users          # một bảng
.\.venv\Scripts\python.exe db_viewer.py query "SELECT model, COUNT(*) FROM predictions GROUP BY model"
.\.venv\Scripts\python.exe db_viewer.py export              # mọi bảng ra .xlsx
```

Phiên kết nối là chỉ đọc và mỗi lần chạy đúng một câu lệnh. Thời gian hiển thị theo giờ Việt Nam (CSDL lưu UTC).

**Cách 3 — công cụ có giao diện:** DBeaver / pgAdmin / VS Code (extension PostgreSQL) với cùng External URL,
bật SSL chế độ `require`. Ví dụ lịch sử dự đoán mới nhất:

```sql
SELECT p.id, u.username, p.created_at, p.model, p.input_json, p.predicted_label, p.predicted_value, p.actual_value
FROM predictions p JOIN users u ON u.id = p.user_id
ORDER BY p.id DESC LIMIT 20;
```

### Bảo trì

- **CSDL Free hết hạn sau 30 ngày** (Render gửi email báo trước). Trước hạn, sao lưu bằng
  `db_viewer.py export`. Sau đó tạo CSDL Free mới và cập nhật `DATABASE_URL` (Cách B), hoặc với Blueprint:
  xoá CSDL cũ rồi bấm **Manual sync** ở trang Blueprint để Render tạo lại theo `render.yaml`. CSDL mới trống,
  app tự tạo lại bảng, `demo`, `admin` và lần train đầu.
- **Đổi mật khẩu admin**: sửa `ADMIN_PASSWORD` ở tab Environment → **Save, rebuild, and deploy**.
- **Đổi mật khẩu CSDL** (khi URL bị lộ): trang CSDL trên Render → đổi credentials. Sau đó mở `/db/health`
  để kiểm tra; nếu lỗi kết nối thì cập nhật `DATABASE_URL` (Cách B) hoặc bấm **Manual sync** Blueprint (Cách A).
- **Giới hạn IP truy cập CSDL từ ngoài**: trang CSDL → **Networking** → Inbound IP Rules (mặc định cho phép mọi IP).

### Lỗi thường gặp

| Hiện tượng | Nguyên nhân / cách sửa |
|---|---|
| `/db/health` trả `"database": "app.db"` | thiếu `DATABASE_URL` → thêm biến rồi deploy lại |
| Log báo `could not translate host name "dpg-...-a"` | dùng Internal URL nhưng CSDL khác region với web service, hoặc dùng Internal URL từ máy mình (từ ngoài Render phải dùng External URL) |
| Đăng nhập `admin` bị 401 | `ADMIN_PASSWORD` chưa có lúc app khởi động → kiểm tra biến rồi **Manual Deploy → Restart service** |
| Trang Dữ liệu SQL báo "Chỉ dành cho quản trị viên" | đang đăng nhập `demo` hoặc tài khoản thường → đăng xuất, vào lại bằng `admin` |
| Không thấy mục "Dữ liệu SQL" ở thanh bên | trình duyệt còn giữ giao diện cũ từ trước commit `b299421` → nhấn **Ctrl + F5** một lần (từ bản đó file giao diện luôn được kiểm tra lại) |
| Build xanh nhưng app không lên, log `FileNotFoundError: svm_model.pkl` | chưa commit tệp mô hình |
| Treo ở "Deploying" | Start Command thiếu `--host 0.0.0.0 --port $PORT` |
| Tạo CSDL báo đã hết lượt Free | workspace đã có 1 CSDL Free → xoá cái cũ hoặc dùng workspace khác |

## Cấu trúc thư mục

```
iris-fastapi/
├── app.py                # MODULE API MÔ HÌNH (+ chế độ gộp cho Render)
├── regression_api.py     # router /regression/*, /dataset/summary và /dataset/pca
├── regression.py         # 5 mô hình hồi quy: train, đánh giá, đo thời gian, đấu trường
├── dataset.py            # thống kê theo loài cho trang Tổng quan
├── train.py              # huấn luyện SVM + sinh metrics.json
├── train_regression.py   # huấn luyện 5 mô hình hồi quy
├── data_loader.py        # nạp dữ liệu Kaggle (kagglehub), fallback sklearn
├── figures.py            # sinh 8 hình cho báo cáo
├── figures_regression.py # sinh 3 hình hồi quy cho báo cáo (từ regression_metrics.json)
├── species.py            # thông tin 3 loài + nguồn ảnh
├── settings.py           # đọc .env / biến môi trường
├── security.py           # bcrypt + JWT
├── seed.py               # train lần đầu + tài khoản demo
├── db_viewer.py          # xem CSDL Render bằng External Database URL (chỉ đọc)
├── db_api/               # MODULE API CSDL
│   ├── main.py           #   app FastAPI + CORS
│   ├── auth.py history.py runs.py export.py
│   ├── db.py             #   kết nối SQLite / PostgreSQL + chạy migration
│   └── migrations/       #   001_initial.sql, ... (+ postgres/ cho PostgreSQL)
├── web/                  # MODULE WEB
│   ├── server.py         #   server tĩnh + /config.js (địa chỉ 2 API)
│   └── public/           #   index.html, css/, js/, vendor/ (Chart.js, giấy phép), fonts/
├── tests/                # pytest
├── svm_model.pkl  metrics.json                   # SVM (PHẢI commit)
├── regression_models.pkl  regression_metrics.json # hồi quy (PHẢI commit)
├── requirements.txt  requirements-dev.txt  pytest.ini
├── render.yaml  Procfile  .env.example
├── data/Iris.csv         # dữ liệu Kaggle uciml/iris (app.db của SQLite cũng nằm đây, không commit)
├── static/images/        # ảnh 3 loài (Wikimedia Commons)
├── CREDITS.md            # nguồn ảnh, icon, font, thư viện, dữ liệu
├── run.sh                # cài + seed + chạy bằng một lệnh (Git Bash)
└── run.ps1               # bản tương đương cho PowerShell
```

Hình cho tài liệu LaTeX (`figures/`) chỉ giữ ở máy và tái tạo được bằng `python figures.py`
và `python figures_regression.py`.

## Ghi chú kỹ thuật

- **Chuẩn hoá nằm trong pipeline** (`StandardScaler` → mô hình) nên API không phải tự tiền xử lý
  và không có rò rỉ dữ liệu giữa các fold khi kiểm định chéo.
- **Xác suất SVM** lấy từ `CalibratedClassifierCV` (Platt scaling) thay cho
  `SVC(probability=True)` đã bị deprecated ở scikit-learn 1.9. Bản hiệu chuẩn cho dự đoán
  trùng 100% với SVC gốc trên tập kiểm tra.
- **Thời gian chạy** đo bằng `time.perf_counter` trên máy chủ: thời gian train = fit cấu hình tốt nhất;
  predict/mẫu = trung bình 200 lần dự đoán cả tập test; đấu trường = trung vị 5 lần gọi sau 1 lần khởi động.
- **Phiên bản thư viện được khoá chính xác** trong `requirements.txt`; phiên bản scikit-learn
  khi chạy phải trùng lúc huấn luyện, nếu không tệp `.pkl` sẽ cảnh báo hoặc lỗi.
- **Dữ liệu Kaggle và scikit-learn lệch nhau 2 dòng** (35 và 38) do lỗi sao chép trong kho UCI;
  chi tiết trong `metrics.json → data.source_comparison`.

Nguồn ảnh, icon (Lucide), font (Be Vietnam Pro), Chart.js và dữ liệu: xem **`CREDITS.md`**.
