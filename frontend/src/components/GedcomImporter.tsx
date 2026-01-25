import { useState, useRef, useCallback } from 'react';
import { Upload, FileText, CheckCircle, AlertCircle } from 'lucide-react';
import { Individual, GedcomUploadResponse } from '../types';

interface GedcomImporterProps {
  onLoaded: (individuals: Individual[]) => void;
}

export default function GedcomImporter({ onLoaded }: GedcomImporterProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<{
    success: boolean;
    message: string;
    count?: number;
  } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleUpload = async (file: File) => {
    console.log('[GedcomImporter] Uploading file:', file.name, 'size:', file.size);
    
    if (!file.name.endsWith('.ged') && !file.name.endsWith('.gedcom')) {
      console.warn('[GedcomImporter] Invalid file type:', file.name);
      setUploadResult({
        success: false,
        message: 'Please upload a valid GEDCOM file (.ged or .gedcom)',
      });
      return;
    }

    setIsUploading(true);
    setUploadResult(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      console.log('[GedcomImporter] Sending upload request...');
      const response = await fetch('/api/upload-gedcom', {
        method: 'POST',
        body: formData,
      });

      console.log('[GedcomImporter] Upload response status:', response.status);

      if (!response.ok) {
        const error = await response.json();
        console.error('[GedcomImporter] Upload error:', error);
        throw new Error(error.detail || 'Upload failed');
      }

      const data: GedcomUploadResponse = await response.json();
      console.log('[GedcomImporter] Upload success:', data.individual_count, 'individuals');
      console.log('[GedcomImporter] Sample individuals:', data.individuals.slice(0, 3));
      
      setUploadResult({
        success: true,
        message: data.message,
        count: data.individual_count,
      });

      onLoaded(data.individuals);
    } catch (error) {
      setUploadResult({
        success: false,
        message: error instanceof Error ? error.message : 'Upload failed',
      });
    } finally {
      setIsUploading(false);
    }
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const file = e.dataTransfer.files[0];
    if (file) {
      handleUpload(file);
    }
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleUpload(file);
    }
  }, []);

  const handleClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="space-y-6">
      <div className="text-center mb-8">
        <h2 className="text-3xl font-bold text-white mb-2">
          Import Your Family Tree
        </h2>
        <p className="text-slate-400">
          Upload a GEDCOM file to start exploring your ancestry with AI-powered research
        </p>
      </div>

      {/* Drop Zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={handleClick}
        className={`drop-zone cursor-pointer ${isDragging ? 'active' : ''}`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".ged,.gedcom"
          onChange={handleFileSelect}
          className="hidden"
        />

        {isUploading ? (
          <div className="flex flex-col items-center gap-4">
            <div className="spinner w-12 h-12"></div>
            <p className="text-slate-300">Parsing GEDCOM file...</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-4">
            <div className="w-16 h-16 rounded-full bg-slate-700 flex items-center justify-center">
              <Upload className="w-8 h-8 text-emerald-500" />
            </div>
            <div>
              <p className="text-lg text-white mb-1">
                Drop your GEDCOM file here
              </p>
              <p className="text-sm text-slate-400">
                or click to browse
              </p>
            </div>
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <FileText className="w-4 h-4" />
              <span>Supports .ged and .gedcom files</span>
            </div>
          </div>
        )}
      </div>

      {/* Upload Result */}
      {uploadResult && (
        <div
          className={`flex items-center gap-3 p-4 rounded-lg ${
            uploadResult.success
              ? 'bg-emerald-500/10 border border-emerald-500/20'
              : 'bg-red-500/10 border border-red-500/20'
          }`}
        >
          {uploadResult.success ? (
            <CheckCircle className="w-5 h-5 text-emerald-500 flex-shrink-0" />
          ) : (
            <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
          )}
          <div>
            <p className={uploadResult.success ? 'text-emerald-400' : 'text-red-400'}>
              {uploadResult.message}
            </p>
            {uploadResult.count && (
              <p className="text-sm text-slate-400 mt-1">
                Found {uploadResult.count} individuals in your family tree
              </p>
            )}
          </div>
        </div>
      )}

      {/* Info Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-8">
        <div className="bg-slate-800 rounded-lg p-4">
          <h3 className="font-semibold text-white mb-2">📊 Visualize</h3>
          <p className="text-sm text-slate-400">
            View your family tree as an interactive ancestor chart
          </p>
        </div>
        <div className="bg-slate-800 rounded-lg p-4">
          <h3 className="font-semibold text-white mb-2">🔍 Research</h3>
          <p className="text-sm text-slate-400">
            AI agent searches Wikipedia, historical newspapers, and more
          </p>
        </div>
        <div className="bg-slate-800 rounded-lg p-4">
          <h3 className="font-semibold text-white mb-2">📚 Sources</h3>
          <p className="text-sm text-slate-400">
            Get cited sources from Wikidata, Chronicling America, and Google Books
          </p>
        </div>
      </div>

      {/* Sample File Info */}
      <div className="text-center text-sm text-slate-500 mt-6">
        <p>
          Don't have a GEDCOM file?{' '}
          <a
            href="/sample-family.ged"
            download
            className="text-emerald-400 hover:text-emerald-300 underline"
          >
            Download our sample file
          </a>
          {' '}to try TreePilot
        </p>
      </div>
    </div>
  );
}
