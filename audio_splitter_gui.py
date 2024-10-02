#!/usr/bin/env python3

import os
import sys
import logging
import traceback  # To capture stack traces
import threading  # For running tasks in separate threads
import queue  # For thread-safe communication
from tkinter import Tk, Label, Entry, Button, StringVar, IntVar, filedialog, messagebox
from tkinter import ttk  # For the Progressbar widget
from pydub import AudioSegment
from pydub.utils import which  # Ensure this import is present
import subprocess  # To run ffprobe
import json  # For configuration persistence


# Function to get the root directory of the application
def get_application_root():
    if getattr(sys, "frozen", False):
        # If the application is run as a bundled executable
        return sys._MEIPASS
    else:
        # If the application is run as a script
        return os.path.dirname(os.path.abspath(__file__))


# Configure logging to write to a file inside the application root and to the console
def setup_logging():
    try:
        log_file_path = os.path.join(get_application_root(), "app.log")
        logging.basicConfig(
            level=logging.DEBUG,  # Set to DEBUG to capture all levels
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(log_file_path),
                logging.StreamHandler(sys.stdout),
            ],
        )
    except Exception as e:
        # If logging setup fails, output to console and proceed
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
        )
        logging.error(f"Failed to set up logging to file: {e}")


setup_logging()
logger = logging.getLogger(__name__)

# Initialize last used directories to the user's home directory
last_input_dir = os.path.expanduser("~")
last_output_dir = os.path.expanduser("~")


# Function to get the paths to FFmpeg and FFprobe
def get_ffmpeg_paths():
    """
    Attempt to locate the FFmpeg and FFprobe executables in the application directory or common installation paths.
    """
    app_root = get_application_root()

    # Paths to ffmpeg and ffprobe in the bundled app
    ffmpeg_in_app = os.path.join(app_root, "ffmpeg", "ffmpeg")
    ffprobe_in_app = os.path.join(app_root, "ffmpeg", "ffprobe")
    if os.name == "nt":
        ffmpeg_in_app += ".exe"  # Add .exe extension on Windows
        ffprobe_in_app += ".exe"

    ffmpeg_path = None
    ffprobe_path = None

    if os.path.exists(ffmpeg_in_app):
        ffmpeg_path = ffmpeg_in_app
        logger.debug(f"Found FFmpeg in app directory: {ffmpeg_path}")
    if os.path.exists(ffprobe_in_app):
        ffprobe_path = ffprobe_in_app
        logger.debug(f"Found FFprobe in app directory: {ffprobe_path}")

    # If not found, try to find ffmpeg and ffprobe in the system PATH
    if ffmpeg_path is None or ffprobe_path is None:
        ffmpeg_path = which("ffmpeg") if ffmpeg_path is None else ffmpeg_path
        ffprobe_path = which("ffprobe") if ffprobe_path is None else ffprobe_path

    # If still not found, check common installation directories
    possible_locations = [
        "/usr/local/bin",  # Homebrew default path
        "/opt/homebrew/bin",  # Homebrew on Apple Silicon Macs
        "/usr/bin",  # Common Linux path
        "/usr/local/ffmpeg/bin",  # Alternative location
    ]

    for path in possible_locations:
        if ffmpeg_path is None and os.path.exists(os.path.join(path, "ffmpeg")):
            ffmpeg_path = os.path.join(path, "ffmpeg")
            logger.debug(f"Found FFmpeg in possible location: {ffmpeg_path}")
        if ffprobe_path is None and os.path.exists(os.path.join(path, "ffprobe")):
            ffprobe_path = os.path.join(path, "ffprobe")
            logger.debug(f"Found FFprobe in possible location: {ffprobe_path}")

    if ffmpeg_path:
        logger.info(f"Using FFmpeg at: {ffmpeg_path}")
    else:
        logger.error("FFmpeg not found.")

    if ffprobe_path:
        logger.info(f"Using FFprobe at: {ffprobe_path}")
    else:
        logger.error("FFprobe not found.")

    return ffmpeg_path, ffprobe_path


# Helper function to get bits per sample using ffprobe
def get_bits_per_sample(file_path):
    """
    Use ffprobe to get the bits per sample of the audio file.
    """
    try:
        cmd = [
            AudioSegment.ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=bits_per_sample",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            file_path,
        ]
        logger.debug(f"Running ffprobe command: {' '.join(cmd)}")
        output = subprocess.check_output(cmd).decode().strip()
        bits_per_sample = int(output)
        logger.debug(f"Bits per sample for '{file_path}': {bits_per_sample}")
        return bits_per_sample
    except subprocess.CalledProcessError as e:
        logger.error(f"ffprobe error for '{file_path}': {e}")
        logger.debug(traceback.format_exc())
        return None
    except Exception as e:
        logger.error(f"Error getting bits per sample for '{file_path}': {e}")
        logger.debug(traceback.format_exc())
        return None


# Helper function to map bits_per_sample to sample_fmt
def get_sample_fmt(bits_per_sample):
    """
    Map bits_per_sample to FFmpeg's sample_fmt.
    """
    mapping = {
        8: "s8",
        16: "s16",
        24: "s24",
        32: "s32",
    }
    sample_fmt = mapping.get(bits_per_sample, None)
    if sample_fmt is None:
        logger.error(f"Unsupported bits per sample: {bits_per_sample}")
    else:
        logger.debug(
            f"Mapped bits_per_sample {bits_per_sample} to sample_fmt {sample_fmt}"
        )
    return sample_fmt


# Function to extract metadata using ffprobe
def get_metadata(file_path):
    """
    Extract all metadata from the audio file using ffprobe.
    """
    try:
        cmd = [
            AudioSegment.ffprobe,
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            file_path,
        ]
        logger.debug(f"Running ffprobe for metadata: {' '.join(cmd)}")
        output = subprocess.check_output(cmd).decode()
        metadata = json.loads(output).get("format", {}).get("tags", {})
        logger.debug(f"Extracted metadata for '{file_path}': {metadata}")
        return metadata
    except subprocess.CalledProcessError as e:
        logger.error(f"ffprobe error for metadata extraction of '{file_path}': {e}")
        logger.debug(traceback.format_exc())
        return {}
    except Exception as e:
        logger.error(f"Error extracting metadata from '{file_path}': {e}")
        logger.debug(traceback.format_exc())
        return {}


# Set the FFmpeg and FFprobe paths for pydub
ffmpeg_path, ffprobe_path = get_ffmpeg_paths()
if ffmpeg_path is None or ffprobe_path is None:
    # Instead of showing a message box here, enqueue the message
    # Assuming message_queue is initialized later, this needs to be handled
    # For simplicity, we'll log and exit
    logger.critical("FFmpeg and/or FFprobe not found. Exiting application.")
    sys.exit(1)
else:
    AudioSegment.converter = ffmpeg_path
    AudioSegment.ffprobe = ffprobe_path
    logger.info(f"FFmpeg and FFprobe paths set successfully.")


def split_audio_files(
    input_dir, output_dir, progress_var, progress_bar, total_files, message_queue
):
    logger.debug("Starting split_audio_files function.")
    try:
        # Re-confirm FFmpeg availability inside the function (optional but safe)
        if AudioSegment.converter is None or AudioSegment.ffprobe is None:
            logger.error("FFmpeg and/or FFprobe not found.")
            message_queue.put(("error", "Error", "FFmpeg and/or FFprobe not found."))
            return

        # Check if input directory exists
        if not os.path.isdir(input_dir):
            logger.error(f"Input directory '{input_dir}' does not exist.")
            message_queue.put(
                ("error", "Error", f"Input directory '{input_dir}' does not exist.")
            )
            return

        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        logger.debug(f"Output directory '{output_dir}' is ready.")

        # Get list of .wav files in the input directory
        wav_files = [
            f
            for f in os.listdir(input_dir)
            if os.path.isfile(os.path.join(input_dir, f)) and f.lower().endswith(".wav")
        ]
        if not wav_files:
            logger.error(f"No .wav files found in directory '{input_dir}'.")
            message_queue.put(
                ("error", "Error", f"No .wav files found in directory '{input_dir}'.")
            )
            return

        logger.info(f"Found {len(wav_files)} .wav file(s) to process.")

        for idx, wav_file in enumerate(wav_files):
            input_file = os.path.join(input_dir, wav_file)
            logger.info(f"Processing file: {input_file}")

            # Update progress
            progress = int(((idx + 1) / total_files) * 100)
            progress_var.set(progress)
            progress_bar["value"] = progress
            progress_bar.update_idletasks()

            # Load the audio file
            try:
                audio = AudioSegment.from_file(input_file)
                logger.debug(f"Loaded audio file '{input_file}' successfully.")
            except Exception as e:
                logger.error(f"Error loading audio file '{input_file}': {e}")
                logger.debug(traceback.format_exc())
                message_queue.put(
                    ("error", "Error", f"Error loading audio file '{input_file}': {e}")
                )
                continue

            # Extract metadata using ffprobe
            metadata = get_metadata(input_file)

            # Extract original audio properties using FFprobe
            bits_per_sample = get_bits_per_sample(input_file)
            if bits_per_sample is None:
                message_queue.put(
                    ("error", "Error", f"Could not determine bit depth of '{wav_file}'")
                )
                continue

            original_frame_rate = audio.frame_rate
            original_channels = audio.channels
            logger.info(f"Original sample rate: {original_frame_rate} Hz")
            logger.info(f"Original bit depth: {bits_per_sample} bits")
            logger.info(f"Number of channels in '{wav_file}': {original_channels}")

            # Split the audio into individual mono channels
            try:
                channels = audio.split_to_mono()
                logger.debug(f"Split audio into {len(channels)} mono channel(s).")
            except Exception as e:
                logger.error(f"Error splitting channels for '{wav_file}': {e}")
                logger.debug(traceback.format_exc())
                message_queue.put(
                    (
                        "error",
                        "Error",
                        f"Error splitting channels for '{wav_file}': {e}",
                    )
                )
                continue

            for channel_idx, channel in enumerate(channels):
                channel_number = channel_idx + 1

                # Determine sample_fmt based on bits_per_sample
                sample_fmt = get_sample_fmt(bits_per_sample)
                if sample_fmt is None:
                    logger.error(
                        f"Unsupported bit depth: {bits_per_sample} bits in '{wav_file}'"
                    )
                    message_queue.put(
                        (
                            "error",
                            "Error",
                            f"Unsupported bit depth: {bits_per_sample} bits in '{wav_file}'",
                        )
                    )
                    continue

                # Determine codec based on sample_fmt
                codec_mapping = {
                    "s8": "pcm_s8",
                    "s16": "pcm_s16le",
                    "s24": "pcm_s24le",
                    "s32": "pcm_s32le",
                }
                codec = codec_mapping.get(
                    sample_fmt, "pcm_s16le"
                )  # Default to 'pcm_s16le'
                logger.debug(f"Using codec '{codec}' for sample_fmt '{sample_fmt}'.")

                # Prepare output filename
                base_name, _ = os.path.splitext(wav_file)
                output_filename = f"{base_name}_chan{channel_number}.wav"
                output_file = os.path.join(output_dir, output_filename)
                logger.debug(f"Output file will be '{output_file}'.")

                # Set frame rate
                channel = channel.set_frame_rate(original_frame_rate)
                logger.debug(
                    f"Set frame rate to {original_frame_rate} Hz for channel {channel_number}."
                )

                # Export the mono channel with correct codec
                try:
                    channel.export(
                        output_file,
                        format="wav",
                        parameters=["-c:a", codec],  # Removed "-sample_fmt", "s24"
                    )
                    logger.info(f"Exported: {output_file}")
                except Exception as e:
                    logger.error(f"Error exporting file '{output_file}': {e}")
                    logger.debug(traceback.format_exc())
                    message_queue.put(
                        ("error", "Error", f"Error exporting file '{output_file}': {e}")
                    )

        # Final progress update
        progress_var.set(100)
        progress_bar["value"] = 100
        progress_bar.update_idletasks()

        # After successfully processing all files
        message_queue.put(
            (
                "info",
                "Success",
                f"Audio files have been successfully split.\nOutput Directory: {output_dir}",
            )
        )

    except Exception as e:
        logger.error(f"An unexpected error occurred in split_audio_files: {e}")
        logger.debug(traceback.format_exc())
        message_queue.put(("error", "Error", f"An unexpected error occurred:\n{e}"))


def browse_input_dir(message_queue):
    global last_input_dir, last_output_dir  # Declare both as global
    try:
        directory = filedialog.askdirectory(initialdir=last_input_dir)
        if directory:
            input_dir_var.set(directory)
            logger.debug(f"Selected input directory: {directory}")
            last_input_dir = directory
            last_output_dir = (
                directory  # Update output initialdir to the selected input directory
            )
    except Exception as e:
        logger.error(f"Error selecting input directory: {e}")
        logger.debug(traceback.format_exc())
        message_queue.put(("error", "Error", f"Error selecting input directory: {e}"))


def browse_output_dir(message_queue):
    global last_output_dir, last_input_dir  # Declare both as global
    try:
        directory = filedialog.askdirectory(initialdir=last_output_dir)
        if directory:
            output_dir_var.set(directory)
            logger.debug(f"Selected output directory: {directory}")
            last_output_dir = directory
            last_input_dir = (
                directory  # Update input initialdir to the selected output directory
            )
    except Exception as e:
        logger.error(f"Error selecting output directory: {e}")
        logger.debug(traceback.format_exc())
        message_queue.put(("error", "Error", f"Error selecting output directory: {e}"))


def run_splitter(message_queue):
    logger.debug("run_splitter function called.")
    try:
        input_dir = input_dir_var.get()
        output_dir = output_dir_var.get()
        logger.debug(f"Input Directory: {input_dir}")
        logger.debug(f"Output Directory: {output_dir}")
        if not input_dir or not output_dir:
            logger.error("Input or output directory not selected.")
            message_queue.put(
                ("error", "Error", "Please select both input and output directories.")
            )
            return

        # Disable the split button to prevent multiple clicks
        split_button.config(state="disabled")

        # Start the split process in a separate thread
        threading.Thread(
            target=split_audio_files_thread,
            args=(input_dir, output_dir, message_queue),
            daemon=True,
        ).start()
    except Exception as e:
        logger.error(f"Error in run_splitter: {e}")
        logger.debug(traceback.format_exc())
        message_queue.put(("error", "Error", f"An unexpected error occurred:\n{e}"))


def open_output_directory(output_dir):
    try:
        if os.name == "nt":  # For Windows
            os.startfile(output_dir)
        elif sys.platform == "darwin":  # For macOS
            subprocess.Popen(["open", output_dir])
        else:  # For Linux and other OS
            subprocess.Popen(["xdg-open", output_dir])
        logger.debug(f"Opened output directory: {output_dir}")
    except Exception as e:
        logger.error(f"Failed to open output directory '{output_dir}': {e}")
        logger.debug(traceback.format_exc())
        messagebox.showerror("Error", f"Failed to open output directory:\n{e}")


def split_audio_files_thread(input_dir, output_dir, message_queue):
    try:
        total_files = (
            len(
                [
                    f
                    for f in os.listdir(input_dir)
                    if os.path.isfile(os.path.join(input_dir, f))
                    and f.lower().endswith(".wav")
                ]
            )
            * 6
        )  # Assuming 6 channels as per your log
        if total_files == 0:
            total_files = 1  # Prevent division by zero

        # Update progress bar settings
        progress_var.set(0)
        progress_bar["value"] = 0
        progress_bar["maximum"] = 100

        # Start splitting files
        split_audio_files(
            input_dir,
            output_dir,
            progress_var,
            progress_bar,
            total_files,
            message_queue,
        )

        # Enqueue success message
        message_queue.put(
            ("info", "Success", "Audio files have been successfully split.")
        )

    except Exception as e:
        logger.error(f"Error in split_audio_files_thread: {e}")
        logger.debug(traceback.format_exc())
        message_queue.put(("error", "Error", f"An unexpected error occurred:\n{e}"))
    finally:
        split_button.config(state="normal")


def main():
    try:
        # Load configuration
        load_config()

        # Initialize last used directories to the loaded configuration
        global last_input_dir, last_output_dir
        # ... existing GUI setup code ...

        # Create the main window
        root = Tk()
        root.title("ZQ SFX Audio Splitter")

        # Create a queue for inter-thread communication
        message_queue = queue.Queue()

        # Handle window close event to save configuration
        root.protocol("WM_DELETE_WINDOW", lambda: on_closing(root, message_queue))

        # Input Directory
        global input_dir_var
        input_dir_var = StringVar()
        Label(root, text="Input Directory:").grid(
            row=0, column=0, sticky="e", padx=5, pady=5
        )
        Entry(root, textvariable=input_dir_var, width=50).grid(
            row=0, column=1, padx=5, pady=5
        )
        Button(
            root, text="Browse...", command=lambda: browse_input_dir(message_queue)
        ).grid(row=0, column=2, padx=5, pady=5)

        # Output Directory
        global output_dir_var
        output_dir_var = StringVar()
        Label(root, text="Output Directory:").grid(
            row=1, column=0, sticky="e", padx=5, pady=5
        )
        Entry(root, textvariable=output_dir_var, width=50).grid(
            row=1, column=1, padx=5, pady=5
        )
        Button(
            root, text="Browse...", command=lambda: browse_output_dir(message_queue)
        ).grid(row=1, column=2, padx=5, pady=5)

        # Progress Bar
        global progress_var, progress_bar
        progress_var = IntVar()
        progress_bar = ttk.Progressbar(
            root,
            orient="horizontal",
            length=400,
            mode="determinate",
            variable=progress_var,
        )
        progress_bar.grid(row=2, column=0, columnspan=3, padx=5, pady=10)

        # Run Button
        global split_button
        split_button = Button(
            root, text="Split Audio Files", command=lambda: run_splitter(message_queue)
        )
        split_button.grid(row=3, column=1, pady=10)

        # Open Output Directory Button (initially disabled)
        global open_output_button
        open_output_button = Button(
            root,
            text="Open Output Directory",
            command=lambda: open_output_directory(output_dir_var.get()),
            state="disabled",
        )
        open_output_button.grid(row=4, column=1, pady=10)  # Adjust row number as needed

        # Function to process messages from the queue
        def process_queue():
            try:
                while True:
                    msg_type, title, message = message_queue.get_nowait()
                    if msg_type == "info":
                        messagebox.showinfo(title, message)
                        # Enable the Open Output Directory button
                        open_output_button.config(state="normal")
                    elif msg_type == "error":
                        messagebox.showerror(title, message)
            except queue.Empty:
                pass
            root.after(100, process_queue)  # Check the queue every 100ms

        # Start processing the queue
        root.after(100, process_queue)

        # Start the GUI event loop
        logger.debug("Starting the Tkinter main loop.")
        root.mainloop()

    except Exception as e:
        logger.error("An unexpected error occurred in main:")
        logger.error(traceback.format_exc())
        messagebox.showerror("Error", f"An unexpected error occurred:\n{e}")
        sys.exit(1)


# Configuration persistence functions
CONFIG_FILE = os.path.join(get_application_root(), "config.json")


def load_config():
    global last_input_dir, last_output_dir
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
                last_input_dir = config.get("last_input_dir", os.path.expanduser("~"))
                last_output_dir = config.get("last_output_dir", os.path.expanduser("~"))
                logger.debug(f"Loaded config: {config}")
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            logger.debug(traceback.format_exc())


def save_config():
    config = {"last_input_dir": last_input_dir, "last_output_dir": last_output_dir}
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)
            logger.debug(f"Saved config: {config}")
    except Exception as e:
        logger.error(f"Error saving config: {e}")
        logger.debug(traceback.format_exc())


# Modify the main function to save config on exit
def on_closing(root, message_queue):
    save_config()
    root.destroy()


if __name__ == "__main__":
    main()
