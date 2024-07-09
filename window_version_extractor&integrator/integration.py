import os
import re
import subprocess
import multiprocessing
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

def get_video_files(input_video_directory_path):
    entries = os.listdir(input_video_directory_path)
    video_files = [entry for entry in entries if entry.endswith(('.mp4', '.avi', '.mkv')) and not entry.startswith('._')]
    return video_files

def extract_number(file_name):
    match = re.search(r'(\d{3})\.', file_name)
    if match:
        return int(match.group(1))
    return -1

def sort_videos_by_number(video_files):
    return sorted(video_files, key=lambda x: extract_number(os.path.basename(x)))

def integration_task(video_file, temp_files_dir, semaphore, queue):
    ffmpeg_path = os.path.join(os.path.dirname(__file__), 'ffmpeg-7.0.1-essentials_build', 'bin', 'ffmpeg.exe')
    base_name = os.path.basename(video_file)
    temp_file = os.path.join(temp_files_dir, base_name + ".temp.mp4")
    ffmpeg_command = [
        ffmpeg_path, '-i', video_file, '-c', 'copy', temp_file
    ]
    try:
        process = subprocess.run(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if process.returncode != 0:
            queue.put((video_file, None, f"Cannot process the file {video_file}: {process.stderr.decode('utf-8')}"))
            semaphore.release()
            return
        queue.put((video_file, temp_file, None))
    except Exception as e:
        queue.put((video_file, None, f"Failed to run FFmpeg command: {str(e)}"))
    semaphore.release()

def video_integration(input_video_directory_path, output_base_name, output_video_name, progress_var, progress_bar):
    video_files = get_video_files(input_video_directory_path)
    if not video_files:
        print("No video files")
        return

    sorted_videos = sort_videos_by_number(video_files)
    sorted_video_paths = [os.path.join(input_video_directory_path, video) for video in sorted_videos]

    output_file = os.path.join(output_base_name, f"{output_video_name}.mp4")

    total_files = len(sorted_video_paths)
    progress_var.set(0)
    progress_bar.config(maximum=total_files)

    queue = multiprocessing.Queue()
    semaphore = multiprocessing.Semaphore(4)  # 限制并发进程数量为 4
    processes = []

    temp_files_dir = os.path.join(output_base_name, "temp_files")
    if not os.path.exists(temp_files_dir):
        os.makedirs(temp_files_dir)

    for video_file in sorted_video_paths:
        semaphore.acquire()
        process = multiprocessing.Process(target=integration_task, args=(video_file, temp_files_dir, semaphore, queue))
        processes.append(process)
        process.start()

    completed_files = 0
    temp_files = []
    errors = []
    while completed_files < total_files:
        video_file, temp_file, error = queue.get()
        if error:
            print(error)
            errors.append(error)
        else:
            temp_files.append((video_file, temp_file))
        completed_files += 1
        progress_var.set(completed_files)
        progress_bar['value'] = completed_files

    for process in processes:
        process.join()

    # 按原始文件顺序排序临时文件
    temp_files.sort(key=lambda x: extract_number(os.path.basename(x[0])))

    filelist_path = os.path.join(output_base_name, 'filelist.txt')
    with open(filelist_path, 'w') as f:
        for _, temp_file in temp_files:
            f.write(f"file '{temp_file}'\n")

    ffmpeg_concat_command = [
        os.path.join(os.path.dirname(__file__), 'ffmpeg-7.0.1-essentials_build', 'bin', 'ffmpeg.exe'), '-f', 'concat', '-safe', '0', '-i', filelist_path, '-c', 'copy', output_file
    ]
    subprocess.run(ffmpeg_concat_command)

    # 清理临时文件和filelist.txt
    for _, temp_file in temp_files:
        os.remove(temp_file)
    os.rmdir(temp_files_dir)
    os.remove(filelist_path)

    print(f"The video has been saved to {output_file}")
    if errors:
        messagebox.showerror("Errors occurred", "\n".join(errors))

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Video Integration")

    folder_path = tk.StringVar()
    output_folder = tk.StringVar()
    output_video_name = tk.StringVar()
    progress_var = tk.IntVar()

    def browse_folder():
        folder_selected = filedialog.askdirectory()
        folder_path.set(folder_selected)

    def browse_output_folder():
        folder_selected = filedialog.askdirectory()
        output_folder.set(folder_selected)

    def start_integration():
        video_folder = folder_path.get()
        base_output = output_folder.get()
        output_name = output_video_name.get()
        if not output_name:
            messagebox.showerror("Error", "Please enter the output video name.")
            return

        video_files = get_video_files(video_folder)
        if not video_files:
            messagebox.showerror("Error", "No video files found in the selected folder.")
            return

        progress_var.set(0)
        progress_bar.config(maximum=len(video_files))
        video_integration(video_folder, base_output, output_name, progress_var, progress_bar)

    tk.Label(root, text="Video Folder:").grid(row=0, column=0, padx=10, pady=10)
    tk.Entry(root, textvariable=folder_path, width=50).grid(row=0, column=1, padx=10, pady=10)
    tk.Button(root, text="Browse", command=browse_folder).grid(row=0, column=2, padx=10, pady=10)

    tk.Label(root, text="Base Output Folder:").grid(row=1, column=0, padx=10, pady=10)
    tk.Entry(root, textvariable=output_folder, width=50).grid(row=1, column=1, padx=10, pady=10)
    tk.Button(root, text="Browse", command=browse_output_folder).grid(row=1, column=2, padx=10, pady=10)

    tk.Label(root, text="Output Video Name:").grid(row=2, column=0, padx=10, pady=10)
    tk.Entry(root, textvariable=output_video_name, width=50).grid(row=2, column=1, padx=10, pady=10)

    tk.Button(root, text="Start Integration", command=start_integration).grid(row=3, column=0, columnspan=3, padx=10, pady=20)

    progress_label = ttk.Label(root, textvariable=progress_var)
    progress_label.grid(row=4, column=0, columnspan=3, padx=10, pady=10)

    progress_bar = ttk.Progressbar(root, orient="horizontal", length=400, mode="determinate", maximum=100)
    progress_bar.grid(row=5, column=0, columnspan=3, padx=10, pady=10)

    root.mainloop()

