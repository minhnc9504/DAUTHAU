import os
import subprocess
import sys

def run_app():
    # 1. Định vị thư mục
    current_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(current_dir)
    python_exe = sys.executable

    print("="*50)
    print("🚀 ĐANG KHỞI ĐỘNG HỆ THỐNG GỢI Ý GÓI THẦU")
    print("="*50)

    # 2. Cập nhật dữ liệu & AI
    try:
        print("🔄 Bước 1: Đang đồng bộ dữ liệu từ CSV...")
        # Không dùng capture_output để nếu có lỗi (do mở Excel) nó hiện ra ngay cho bạn thấy
        subprocess.run([python_exe, "convert_data.py"], check=True)
        
        print("🧠 Bước 2: Đang cập nhật bộ não AI...")
        subprocess.run([python_exe, "train_model.py"], check=True)
        
        print("✅ Cập nhật hoàn tất!")
    except Exception as e:
        print(f"⚠️ Cảnh báo: Không thể cập nhật dữ liệu tự động. Lý do: {e}")
        print("Hệ thống sẽ chạy với dữ liệu cũ nhất có thể.")

    print("\n🌐 Bước 3: Đang mở giao diện trên trình duyệt...")
    cmd = [python_exe, "-m", "streamlit", "run", "app.py"]
    
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n👋 Đã đóng ứng dụng.")

if __name__ == "__main__":
    run_app()