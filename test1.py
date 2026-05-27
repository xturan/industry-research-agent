def print_multiplication_table():
    for i in range(1, 10):
        for j in range(1, i + 1):
            print(f"{j}×{i}={i*j}", end="\t")
        print()  # 换行

if __name__ == "__main__":
    print_multiplication_table()
    