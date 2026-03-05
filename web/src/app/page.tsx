'use client';

import { useEffect, useState, type ChangeEvent, type DragEvent } from 'react';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { usePipelineStore, useIsLoading } from '@/stores/pipeline-store';
import { FileSearch, AlertCircle, Globe, FileText, ImagePlus, X } from 'lucide-react';
import type { ImageInput } from '@/types';

const MAX_IMAGE_COUNT = 5;

async function fileToBase64(file: File): Promise<string> {
  const arrayBuffer = await file.arrayBuffer();
  let binary = '';
  const bytes = new Uint8Array(arrayBuffer);
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...chunk);
  }
  return btoa(binary);
}

export default function HomePage() {
  const router = useRouter();
  const {
    text,
    images,
    error,
    setText,
    setImages,
    runPipeline,
    crawlUrl,
    restorableTaskId,
    restorableUpdatedAt,
    hydrateFromLatest,
  } = usePipelineStore();
  const isLoading = useIsLoading();

  const [url, setUrl] = useState('');
  const [restoreDisabled, setRestoreDisabled] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  
  useEffect(() => {
    try {
      setRestoreDisabled(sessionStorage.getItem('truthcast_restore_disabled') === '1');
    } catch {
      setRestoreDisabled(false);
    }
  }, []);

  const handleRun = async () => {
    if (!text.trim() && images.length === 0) {
      toast.warning('请输入待分析的文本或上传图片');
      return;
    }
    router.push('/result');
    runPipeline();
  };

  const appendImages = async (files: File[]) => {
    if (files.length === 0) return;
    const available = Math.max(0, MAX_IMAGE_COUNT - images.length);
    if (available <= 0) {
      toast.warning(`最多上传 ${MAX_IMAGE_COUNT} 张图片`);
      return;
    }

    const accepted = files.slice(0, available);
    try {
      const encoded: ImageInput[] = [];
      for (const file of accepted) {
        if (!file.type.startsWith('image/')) continue;
        const base64 = await fileToBase64(file);
        encoded.push({ base64, mime_type: file.type || 'image/jpeg' });
      }
      if (encoded.length === 0) {
        toast.warning('未检测到可用图片文件');
      } else {
        setImages([...images, ...encoded]);
        toast.success(`已添加 ${encoded.length} 张图片`);
      }
    } catch {
      toast.error('图片读取失败，请重试');
    }
  };

  const handleImageSelect = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? []);
    await appendImages(files);
    event.target.value = '';
  };

  const handleDrop = async (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragging(false);
    const files = Array.from(event.dataTransfer.files ?? []);
    await appendImages(files);
  };

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
  };

  const removeImage = (index: number) => {
    const next = images.filter((_, i) => i !== index);
    setImages(next);
  };

  const handleCrawl = () => {
    if (!url.trim()) {
      toast.warning('请输入待分析的网页链接');
      return;
    }
    if (!url.startsWith('http')) {
      toast.warning('请输入有效的 URL（以 http:// 或 https:// 开头）');
      return;
    }
    
    router.push('/result');
    crawlUrl(url).catch(() => {});
  };

  return (
    <div className="max-w-3xl mx-auto px-4">
      <Card>
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            <FileSearch className="h-10 w-10 md:h-12 md:w-12 text-primary" />
          </div>
          <CardTitle className="text-xl md:text-2xl">TruthCast 智能研判台</CardTitle>
          <CardDescription className="text-sm md:text-base">
            输入新闻文本或网页链接，系统将分阶段返回风险快照、主张抽取、证据链与综合报告。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <Tabs defaultValue="text" className="w-full">
            <TabsList className="grid w-full grid-cols-2 mb-4">
              <TabsTrigger value="text" className="flex items-center gap-2">
                <FileText className="h-4 w-4" />
                新闻分析
              </TabsTrigger>
              <TabsTrigger value="url" className="flex items-center gap-2">
                <Globe className="h-4 w-4" />
                链接核查
              </TabsTrigger>
            </TabsList>
            
            <TabsContent value="text" className="space-y-4">
              <Textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="请输入待分析的文本..."
                rows={6}
                className="resize-none text-base"
              />
              <div
                className={`space-y-3 rounded-md border border-dashed p-3 transition-colors ${
                  isDragging ? 'border-primary bg-primary/5' : ''
                }`}
                onDragEnter={() => setIsDragging(true)}
                onDragOver={handleDragOver}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm text-muted-foreground">
                    可选：上传图片辅助核查（最多 {MAX_IMAGE_COUNT} 张，支持拖拽）
                  </div>
                  <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm hover:bg-accent">
                    <ImagePlus className="h-4 w-4" />
                    添加图片
                    <input
                      type="file"
                      accept="image/*"
                      multiple
                      className="hidden"
                      onChange={handleImageSelect}
                      disabled={isLoading || images.length >= MAX_IMAGE_COUNT}
                    />
                  </label>
                </div>
                {images.length > 0 && (
                  <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                    {images.map((image, idx) => {
                      const src = image.base64
                        ? `data:${image.mime_type || 'image/jpeg'};base64,${image.base64}`
                        : image.url || '';
                      return (
                        <div key={`${idx}-${image.mime_type || 'img'}`} className="relative overflow-hidden rounded border bg-muted">
                          {src ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img src={src} alt={`上传图片${idx + 1}`} className="h-24 w-full object-cover" />
                          ) : (
                            <div className="flex h-24 items-center justify-center text-xs text-muted-foreground">图片不可预览</div>
                          )}
                          <button
                            type="button"
                            onClick={() => removeImage(idx)}
                            className="absolute right-1 top-1 rounded bg-background/90 p-1 hover:bg-background"
                            aria-label={`删除图片${idx + 1}`}
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
              <div className="flex justify-center">
                <Button
                  size="lg"
                  onClick={handleRun}
                  disabled={isLoading || (!text.trim() && images.length === 0)}
                  className="w-full sm:w-auto sm:min-w-48"
                >
                  {isLoading ? '分析中...' : '开始分析'}
                </Button>
              </div>
            </TabsContent>
            
            <TabsContent value="url" className="space-y-4">
              <div className="space-y-2">
                <Input
                  type="url"
                  placeholder="请输入新闻或网页链接 (http://...)"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  className="text-base h-12"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleCrawl();
                  }}
                />
                <p className="text-xs text-muted-foreground">
                  系统将自动抓取网页正文、发布日期等关键信息并进入分析流水线。
                </p>
              </div>
              <div className="flex justify-center">
                <Button
                  size="lg"
                  onClick={handleCrawl}
                  disabled={isLoading || !url.trim()}
                  className="w-full sm:w-auto sm:min-w-48"
                  variant="default"
                >
                  {isLoading ? '抓取中...' : '抓取并核查'}
                </Button>
              </div>
            </TabsContent>
          </Tabs>
          
          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {restorableTaskId && restoreDisabled && (
            <div className="pt-2 flex flex-col items-center gap-2 text-sm text-muted-foreground">
              <div>
                已关闭自动恢复提示（本次会话内生效）。
                {restorableUpdatedAt ? ` 可恢复任务更新时间：${restorableUpdatedAt}` : ''}
              </div>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  try {
                    sessionStorage.removeItem('truthcast_restore_disabled');
                  } catch {
                    // ignore
                  }
                  setRestoreDisabled(false);
                  void hydrateFromLatest({ taskId: restorableTaskId, force: true });
                }}
              >
                恢复上一次分析
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
