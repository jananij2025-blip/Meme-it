# Meme-it
### AI-Powered Personalized Meme & Sticker Pack Generator

**Your face. Your memes.**

Meme-it is an AI-powered web application that transforms personal photos into funny, customized memes and downloadable stickers.

**Hackathon:** AI Lodge Hackathon 2026  
**Track:** Projects for Daily Life

**Live Demo:** https://meme-it-beta.vercel.app

**GitHub Repository:** https://github.com/jananij2025-blip/Meme-it

---

## 1. Problem Statement

Memes and stickers are a popular way to communicate online, but creating personalized ones often requires editing software, creativity, and time.

Most meme generators rely on existing templates rather than allowing users to easily turn their own photos into expressive stickers.

Meme-it addresses this by combining AI-powered caption generation with automated image editing, allowing users to create personalized memes without design experience.

## 2. Solution Overview

Meme-it is a web application that transforms uploaded photos into personalized meme stickers.

Users upload a photo, select a theme, generate AI-powered captions, customize their favourite caption, and create a transparent PNG sticker.

Users can also organize their creations into sticker packs and download them as ZIP files.

The application aims to make personalized meme creation accessible, quick, and enjoyable.

## 3. Key Features

### Photo Upload and People Detection
- Upload JPG, PNG, or WebP images.
- Detect people in uploaded photos.
- Choose to feature one person or everyone in a group photo.

### AI-Powered Meme Generation
- Generate five meme caption suggestions.
- Choose from Work, Relationships, Life, Tech, and other themes.
- Enter custom themes.
- Receive personalized theme recommendations.

### Meme Customization
- Select a favourite AI-generated caption.
- Edit captions before creating stickers.
- Customize character labels for group photos.

### Automatic Sticker Creation
- Remove image backgrounds using AI.
- Generate transparent PNG stickers.
- Download individual stickers.

### Sticker Pack Builder
- Collect up to 12 stickers.
- Rearrange or remove stickers.
- Download packs containing 6–12 stickers as ZIP files.

### Personalized Experience
- Track meme selections and sticker creation feedback.
- Use previous interactions to support theme recommendations.

## 4. AI Integration

Meme-it integrates AI into two main parts of its workflow.

**Multimodal Meme Caption Generation**

Gemini, accessed through APIYI, processes the uploaded image together with the selected theme to generate contextually relevant meme captions.

The model can interpret visual context, including expressions, poses, and situations, although it is not a dedicated facial-expression classifier.

**AI Background Removal**

Meme-it uses the `@imgly/background-removal` library to remove image backgrounds directly in the user's browser.

This enables the creation of transparent stickers while reducing server-side processing requirements.

**Personalization**

User interaction history and feedback are used to support personalized theme recommendations.

## 5. External Tools, Technologies and Datasets

| Technology | Purpose |
|---|---|
| React | Frontend user interface |
| TypeScript | Frontend application logic |
| Vite | Frontend build tool |
| Python | Backend programming |
| FastAPI | Backend API |
| Gemini via APIYI | AI-powered caption generation |
| @imgly/background-removal | Browser-based AI background removal |
| Supabase | Personalization and feedback data |
| JSZip | Sticker pack ZIP downloads |
| Vercel | Frontend hosting |
| Render | Backend hosting |
| GitHub | Source code management |

**Datasets:** No custom training dataset is required for the core caption-generation and background-removal workflow. The application uses pretrained AI models.

## 6. Installation and Setup

### Prerequisites

- Node.js and npm
- Python 3
- Git
- APIYI API key
- Supabase project credentials

### Clone the Repository

```bash
git clone https://github.com/jananij2025-blip/Meme-it.git
cd Meme-it
```

### Frontend Setup

```bash
cd frontend
npm install
```

Create a `.env` file inside `frontend`:

```env
VITE_API_URL=http://127.0.0.1:8000
```

Start the frontend:

```bash
npm run dev
```

Open the local URL displayed by Vite, typically `http://localhost:5173`.

### Backend Setup

Open another terminal in the project root:

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment.

Windows:

```powershell
.venv\Scripts\activate
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Configure the required backend environment variables:

```env
APIYI_API_KEY=your_api_key
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

Start the API:

```bash
uvicorn main:app --reload
```

The backend will run at `http://127.0.0.1:8000`.

**Security:** Never commit actual API keys, service-role credentials, or `.env` files to GitHub.

## 7. AI Safety and Limitations

Meme-it has several important considerations for responsible AI use.

### Image Privacy
Users upload personal photos, which may contain identifiable people. Images should only be uploaded with appropriate permission.

The caption-generation workflow sends uploaded image data to the backend and an external AI provider. Background removal runs locally in the browser.

### AI-Generated Content
AI-generated captions may occasionally be inaccurate, irrelevant, or inappropriate.

Users can review, select, and edit captions before generating stickers. This human review is helpful but does not replace automated content moderation.

### Image Processing Limitations
Background removal may produce imperfect results with complex backgrounds, overlapping people, or poor lighting.

Browser-based AI processing may also be slower on devices with limited memory or processing power.

### File Upload Restrictions
The frontend accepts JPG, PNG, and WebP images with a maximum upload size of 10 MB.

These client-side restrictions should be complemented by server-side validation.

### Reliability and Testing
During deployment, server-side background removal exceeded Render's 512 MB memory limit.

To address this, background removal was moved to the browser, reducing the backend's memory requirements during sticker creation.

The application has been manually tested through its deployed meme and sticker creation workflow. Broader automated security, content-safety, and cross-device testing remains future work.

## 8. Challenges and Solutions

**Challenge: Backend memory limitations**

Initially, background removal ran on the FastAPI backend using `rembg`. This caused memory crashes on Render's free hosting instance.

**Solution:** Moved AI background removal to the browser using `@imgly/background-removal`, allowing sticker creation without sending images to the backend for cutout processing.

This experience highlighted the importance of designing AI applications around deployment constraints.

## 9. Future Improvements

- Short and normal caption length options.
- More personalized meme recommendations.
- Additional sticker styles and templates.
- Improved background removal for complex group photos.
- Stronger AI content moderation and safety testing.
- Persistent sticker-pack storage and sharing.
- Better performance on mobile devices.

## 10. Deployment

**Frontend:** Vercel  
https://meme-it-beta.vercel.app

**Backend:** Render  
https://meme-it-backend.onrender.com

**Source Code:** GitHub  
https://github.com/jananij2025-blip/Meme-it

---

**Built for AI Lodge Hackathon 2026.**