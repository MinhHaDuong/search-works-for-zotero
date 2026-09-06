# Tiếng Việt. Bản gốc là locale/en/sdt-pack-sitter.ftl: mọi định danh thiếu ở
# đây sẽ tự động lấy bản tiếng Anh mà không sinh lỗi (ticket 0692).
#
# Đơn vị công việc là MỘT TỆP ĐÍNH KÈM, không phải tài liệu tham chiếu chứa nó.
# Vì vậy mọi câu ở đây đều nói «tệp». «Pack» là tên nội bộ của tạo phẩm và không
# bao giờ hiện ra màn hình.
#
# Tiếng Việt chỉ có một dạng số, nên hai thông điệp phụ thuộc số lượng bên dưới
# chỉ khai báo biến thể mặc định — vẫn qua bộ chọn, để quy tắc số của locale
# quyết định thay vì mã nguồn.

## Nút trên thanh công cụ, và chú giải nó mang theo

index = Chỉ mục
index-coverage = Chỉ mục { $percent } %
scope-one = Thư viện: { $names }
scope-few = Các thư viện: { $names }
scope-many = Tất cả thư viện ({ $count })

files-indexed = { $count ->
       *[other] Đã lập chỉ mục { $count } tệp
    }

## Mọi giai đoạn người đọc có thể gặp khi rê chuột

phase-census = Đang kiểm kê
phase-extracting = Đang lập chỉ mục
phase-error = Lỗi
phase-disabled = Đã tắt
phase-native-worker-busy = Đang chờ: bộ lập chỉ mục gốc đang chạy
phase-cpu-busy = Tạm dừng: bộ xử lý bận
phase-low-memory = Tạm dừng: không đủ bộ nhớ
phase-low-disk = Tạm dừng: không đủ dung lượng đĩa
phase-storage-unavailable = Tạm dừng: không truy cập được kho lưu trữ
phase-resources-unavailable = Tạm dừng: không đọc được tài nguyên hệ thống
phase-launch-declined = Chưa khởi động: hãy tắt rồi bật lại tiện ích

## Khung cửa sổ trạng thái

dialog-title = Trợ lý lập chỉ mục
section-global = Tiến độ tổng thể — thư viện
section-active = Đang lập chỉ mục
details-title = Chi tiết
fulltext-title = Chỉ mục tìm kiếm toàn văn
fulltext-body = Chỉ mục tìm kiếm toàn văn của Zotero (khác với chỉ mục do trợ lý chuẩn bị):
fulltext-unavailable = Không có số liệu: { $error }
tech-title = Chẩn đoán kỹ thuật

## Lớp 1: tiến độ, việc đang chạy, và thời điểm dự kiến kết thúc

files-indexed-of = Tệp đã lập chỉ mục: { $current } / { $total }
files-indexed-count = Tệp đã lập chỉ mục: { $current }
global-estimate = Dự kiến xong khoảng { $median } (từ { $low } đến { $high })
active-none = Không có tiến trình lập chỉ mục
active-file = Đang lập chỉ mục: { $file } — { $progress } % — đã trôi qua { $elapsed }
active-finalising = Đang hoàn tất…
active-references = Đang phân tích phần tham chiếu…
active-estimate = Thời lượng dự kiến: { $median } (từ { $low } đến { $high })

files-failed = { $count ->
       *[other] { $count } tệp không lập chỉ mục được
    }

## Lớp 2: các số đếm, và cơ sở tính của những ước lượng ở trên

observations-waiting = Thời lượng đã quan sát: { $count } (cần 3 trước khi ước lượng)
observations = Thời lượng đã quan sát: { $count }
observations-basis = Thời lượng đã quan sát: { $count } — cơ sở tính: { $basis }
basis-pages = theo trang
basis-bytes = theo byte
diagnostics-phase = Trạng thái: { $phase }
diagnostics-census = Kiểm kê: { $scanned } / { $total }
diagnostics-count = { $status }: { $count }
diagnostics-completed = Tạo trong phiên này: { $count }
diagnostics-failed = Không lập chỉ mục được (lần kiểm kê gần nhất): { $count }
diagnostics-error = Lỗi: { $error }
cache-not-saved = Không lưu được bộ đệm: { $error }

## Lớp 3: thứ một báo cáo lỗi cần đến và người đọc không bao giờ đọc

debug-label = Ghi từng bước vào nhật ký gỡ lỗi của Zotero
journal-copy = Sao chép nhật ký
journal-copied = Đã sao chép nhật ký vào bảng nhớ tạm.
journal-copy-failed = Không sao chép được: bảng nhớ tạm không khả dụng.
journal-unreadable = Không đọc được nhật ký: { $error }
environment-version = Phiên bản tiện ích: { $version }
environment-zotero = Zotero: { $version } (tương thích khai báo { $min } – { $max })
environment-native = Định dạng gốc: phiên bản { $format }, lược đồ { $schema }
environment-extractors = Bộ trích xuất gốc: { $extractors }
environment-root = Cài đặt tại: { $root }
admission-none = Chưa đo tài nguyên lần nào kể từ khi khởi động.
admission-age = Lần đo gần nhất cách đây { $age } — mỗi lần nhận việc đo một lần, không đo khi thư viện đã cập nhật
admission-memory = Bộ nhớ khả dụng: { $available } (ngưỡng { $threshold })
admission-load = Tải bộ xử lý: { $load } trên { $cpus } lõi
admission-disk = Dung lượng đĩa: { $available } (ngưỡng { $threshold })

## Các đại lượng, và cách gọi tên một tệp

gibibytes = { $value } GiB
unknown-value = ?
unit-seconds = { $count } s
unit-minutes = { $count } phút
unit-hours-minutes = { $hours } giờ { $minutes } phút
unit-minutes-seconds = { $minutes } phút { $seconds } s
file-unknown = tệp không rõ
file-number = tệp số { $id }
settle-failed = Lỗi với « { $file } »: { $error }
resources-read = Đọc tài nguyên: { $error }

## Hộp thoại khởi động, thân là bốn thông điệp dưới đây, theo thứ tự

launch-title = Trợ lý lập chỉ mục — thử nghiệm
launch-question = Lập chỉ mục toàn bộ thư viện đêm nay?
launch-conditions = Mỗi lần một tệp, với ít nhất 4 GiB bộ nhớ khả dụng và 8 GiB đĩa trống. Các PDF và thiết lập chỉ mục tìm kiếm toàn văn được giữ nguyên.
launch-worker = Tiến trình dùng chung không thể bị ngắt, cũng không thể nhận mức ưu tiên hệ thống riêng. Một tệp lớn có thể làm chậm công việc gốc đến sau nó. Các ngưỡng không giới hạn mức tiêu thụ của nó.
launch-disable = Tắt tiện ích sẽ dừng nhận việc mới; tệp đang chạy vẫn hoàn tất. Lỗi chỉ tồn tại trong phiên. Một bộ đệm cục bộ dùng một lần lưu các lần kiểm tra và thời lượng; nó không chứa văn bản hay việc đang chạy.
