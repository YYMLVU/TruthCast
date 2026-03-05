'use client';

import { useState } from 'react';
import { ProgressTimeline } from '@/components/layout';
import { RiskOverview, ClaimList, EvidenceChain, ReportCard, ExportButton } from '@/components/features';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { usePipelineStore } from '@/stores/pipeline-store';
import type { Phase } from '@/types';
import { CheckCircle2 } from 'lucide-react';

export default function ResultPage() {
  const [showFullInput, setShowFullInput] = useState(false);
  const {
    text,
    images,
    detectData,
    claims,
    rawEvidences,
    evidences,
    report,
    simulation,
    content,
    phases,
    retryPhase,
    interruptPipeline,
  } = usePipelineStore();

  const hasReport = report !== null;
  const hasInputText = text.trim().length > 0;
  const hasInputImages = images.length > 0;
  const shouldClampInput = text.length > 800;
  const inputPreview = showFullInput || !shouldClampInput ? text : `${text.slice(0, 800)}...`;
  const allDone =
    phases.detect === 'done' &&
    phases.claims === 'done' &&
    phases.evidence === 'done' &&
    phases.report === 'done';

  const handleRetry = (phase: Phase) => {
    retryPhase(phase);
  };

  return (
    <div className="space-y-6 px-2 md:px-0">
      {/* 进度时间线 + 导出按钮 */}
      <div className="flex flex-col items-center gap-4">
        <ProgressTimeline
          phases={phases}
          onRetry={handleRetry}
          onAbort={interruptPipeline}
          showRetry={true}
          mobileMode="collapsible"
          rememberExpandedKey="timeline_result"
        />
        <div className="w-full space-y-3">
          {hasReport && (
            <div className="flex justify-center">
              <ExportButton
                data={{
                  inputText: text,
                  detectData,
                  claims,
                  evidences,
                  report,
                  simulation,
                  content: content ?? null,
                  exportedAt: new Date().toLocaleString('zh-CN'),
                }}
              />
            </div>
          )}

          <div className="rounded-lg border bg-background p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h1 className="font-semibold text-foreground">输入新闻原文</h1>
              <div className="flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  className="text-xs px-2 py-1 rounded border hover:bg-muted"
                  onClick={async () => {
                    if (!hasInputText) return;
                    try {
                      await navigator.clipboard.writeText(text);
                    } catch {
                      // ignore
                    }
                  }}
                  disabled={!hasInputText}
                >
                  复制原文
                </button>
                {shouldClampInput && (
                  <button
                    type="button"
                    className="text-xs px-2 py-1 rounded border hover:bg-muted"
                    onClick={() => setShowFullInput((prev) => !prev)}
                  >
                    {showFullInput ? '收起' : '展开'}
                  </button>
                )}
              </div>
            </div>

            {hasInputText ? (
              <div className="text-sm whitespace-pre-wrap break-words text-muted-foreground max-h-72 overflow-auto">
                {inputPreview}
              </div>
            ) : (
              <div className="text-sm text-muted-foreground">当前无可展示的输入新闻</div>
            )}

            {hasInputImages && (
              <div className="space-y-2">
                <div className="text-sm font-medium text-foreground">输入图片（{images.length} 张）</div>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {images.map((image, idx) => {
                    const src = image.base64
                      ? `data:${image.mime_type || 'image/jpeg'};base64,${image.base64}`
                      : image.url || '';
                    if (!src) return null;

                    return (
                      <Dialog key={`${idx}-${image.mime_type || 'img'}`}>
                        <DialogTrigger asChild>
                          <button
                            type="button"
                            className="group relative overflow-hidden rounded-md border bg-muted text-left"
                            aria-label={`查看输入图片${idx + 1}`}
                          >
                            <div className="flex w-full items-center justify-center bg-muted">
                              {/* eslint-disable-next-line @next/next/no-img-element */}
                              <img
                                src={src}
                                alt={`输入图片${idx + 1}`}
                                className="h-auto w-full object-contain"
                              />
                            </div>
                            <span className="absolute left-1 top-1 rounded bg-background/85 px-1.5 py-0.5 text-[10px] text-muted-foreground">
                              图{idx + 1}
                            </span>
                          </button>
                        </DialogTrigger>
                        <DialogContent className="max-w-4xl">
                          <DialogHeader>
                            <DialogTitle>{`输入图片 ${idx + 1}`}</DialogTitle>
                            <DialogDescription>该图片来自本次检测输入</DialogDescription>
                          </DialogHeader>
                          <div className="max-h-[70vh] overflow-auto rounded border bg-muted p-2">
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img src={src} alt={`输入图片${idx + 1}大图`} className="h-auto w-full object-contain" />
                          </div>
                        </DialogContent>
                      </Dialog>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 分析完成庆祝 banner */}
      {allDone && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-green-50 border border-green-200 text-green-800 text-sm animate-in fade-in duration-700">
          <CheckCircle2 className="h-5 w-5 shrink-0 text-green-600" />
          <span className="font-medium">分析完成！</span>
          <span className="text-green-700">全链路核查已结束，请查看下方各模块结果。</span>
        </div>
      )}

      {/* 风险概览 + 主张抽取 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 md:gap-6">
        <ErrorBoundary title="风险概览加载失败">
          <RiskOverview data={detectData} isLoading={phases.detect === 'running'} />
        </ErrorBoundary>
        <ErrorBoundary title="主张抽取加载失败">
          <ClaimList claims={claims} isLoading={phases.claims === 'running'} />
        </ErrorBoundary>
      </div>

      {/* 证据链 */}
      <ErrorBoundary title="证据链加载失败">
        <EvidenceChain
          rawEvidences={rawEvidences}
          evidences={evidences}
          claims={claims}
          report={report}
          isLoading={phases.evidence === 'running'}
        />
      </ErrorBoundary>

      {/* 综合报告 */}
      <ErrorBoundary title="综合报告加载失败">
        <ReportCard report={report} isLoading={phases.report === 'running'} />
      </ErrorBoundary>
    </div>
  );
}
