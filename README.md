# **CAMpy**

**CAMpy** is a Linux-based digital camera application designed specifically for machine learning researchers and computer vision enthusiasts. Built with Python, PyQt5, and OpenCV, it provides a retro-inspired digital camera interface optimized for rapidly generating image datasets.

This application was designed to create sets of images similar to an old camera. Every shot works as more exposure time, as all the images are ordered in batches specifically formatted for **Variational Autoencoder (VAE) training**. Just adjust the batch size to your neural network training pipeline, set the number of batches, and you're ready to go\!

## **Features**

* **Rapid Batch Capturing:** Instantly shoot (number of batches) \* (batch size) images in a single click.  
* **Pipeline-Ready Naming:** Automatically names files in a highly organized format: \[SessionID\]\_\[Shot\]b\[Batch\]-\[PicNum\].png.  
* **Custom Aspects & Resolutions:** Crop on-the-fly to 1:1, 4:3, or 16:9 aspect ratios at various lens resolutions.  
* **Non-Blocking UI:** Camera feed and thumbnail loading run on separate background threads for a smooth, freeze-free experience.  
* **Interactive Image Roll:** Horizontally scrollable thumbnail gallery that updates instantly as you shoot.  
* **Fullscreen Preview:** Built-in image viewer with keyboard navigation (Left/Right arrows).

## **Installation**

CAMpy requires Python 3.x.

### **1\. Install Dependencies**

To prevent common Qt plugin conflicts on Linux (the infamous xcb error), it is highly recommended to use the **headless** version of OpenCV alongside PyQt5.

Run the following command in your terminal or virtual environment:

pip install PyQt5 opencv-python-headless numpy

*(Note: If you previously had opencv-python installed and encounter GUI errors, uninstall it first: pip uninstall opencv-python)*

### **2\. Download CAMpy**

Clone this repository or download the CAM.py script directly to your local machine.

## **How to Run**

Navigate to the directory containing the script and run:

python CAM.py

## **How to Use**

The interface is divided into easy-to-use panels:

### **Left Panel: Capture Settings**

* **Session ID:** A unique 4-character ID generated for your current runtime to prevent dataset overlapping.  
* **Capture Mode (SINGLE Image):** Toggle this to ignore batch settings and take a single standard photograph.  
* **Number of Batches:** How many groups of images to capture per click.  
* **Batch Size:** How many images are in each batch (align this with your neural network's batch size).

### **Right Panel: Lens Settings**

* **Camera Device:** Switch between available camera inputs (0, 1, 2, 3\) directly from the UI.  
* **Lens Resolution:** Sets the physical capture resolution of your webcam/camera device.  
* **Aspect Format:** Crops the incoming camera feed to 1:1 (ideal for many VAEs), 4:3, or 16:9.  
* **Roll Directory:** Choose where your dataset will be saved. Defaults to \~/CAMpyRoll.

### **Center & Bottom: Shooting and Reviewing**

* **SHOOT Button:** Click to capture. A red LED will appear in the top right of the preview feed indicating that the camera is rapidly writing images to disk.  
* **Image Roll:** The bottom bar shows your saved images. Click any thumbnail to enter **Preview Mode**. In Preview Mode, use the Left and Right arrow keys to browse, and Esc (or the Back button) to return to the camera.

## **Credits**

Created and maintained by **220** \- Website: [2-2-0.online](https://2-2-0.online)

## **License**

This project is licensed under the **MIT license**.

You may copy, distribute and modify the software as long as you track changes/dates in source files. Any modifications to or software including (via compiler) GPL-licensed code must also be made available under the GPL along with build & install instructions.

## **Legal Disclaimer**

THIS SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.