import pandas as pd
import os

def convert():
    input_file = 'data/dauthau_data.csv' 
    output_file = 'data/dauthau_data.parquet'
    
    if not os.path.exists(input_file):
        print(f"❌ Không tìm thấy file: {input_file}")
        return

    print("🚀 Đang đọc dữ liệu gốc...")
    
    # Danh sách các bảng mã phổ biến cho tiếng Việt
    # utf-8-sig là chuẩn nhất khi file CSV được lưu từ Excel
    encodings = ['utf-8-sig', 'utf-8', 'cp1258', 'latin-1']
    df = None
    
    for enc in encodings:
        try:
            df = pd.read_csv(input_file, low_memory=False, encoding=enc)
            # Kiểm tra xem có ký tự lỗi ? trong 10 dòng đầu không
           # if df.iloc[:10, 1].astype(str).str.contains('\?').any() and enc != 'latin-1':
            if df.iloc[:10, 1].astype(str).str.contains(r'\?').any() and enc != 'latin-1':
                continue
            print(f"✅ Đọc thành công với bảng mã: {enc}")
            break
        except:
            continue
            
    if df is not None:
        if 'bidresult' in df.columns:
            df['bidresult'] = df['bidresult'].fillna(0).astype('int8')
        
        df.to_parquet(output_file, compression='snappy', index=False)
        print("✅ Đã chuyển đổi dữ liệu sạch sang Parquet thành công!")
    else:
        print("❌ Không thể đọc file CSV bằng bất kỳ bảng mã nào.")

if __name__ == "__main__":
    convert()