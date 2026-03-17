'use client';

import { useState } from 'react';
import { ProgressTimeline } from '@/components/layout';
import { RiskOverview, ClaimList, EvidenceChain, ReportCard, ExportButton } from '@/components/features';
import { ErrorBoundary } from '@/components/ui/error-boundary';
import { resolveApiUrl } from '@/services/api';
import { usePipelineStore } from '@/stores/pipeline-store';
import type { Phase } from '@/types';
import { CheckCircle2, Sparkles, Layers3 } from 'lucide-react';

export default function ResultPage() {
  const [showFullInput, setShowFullInput] = useState(false);
  const {
    text,
    detectData,
    images,
    fusionReport,
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

          <div className="rounded-lg border bg-background p-4 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h1 className="font-semibold text-foreground">输入新闻</h1>
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

            {images.length > 0 && (
              <div className="space-y-3 border-t pt-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                  <h2 className="text-sm font-medium text-foreground">图片输入</h2>
                  <span className="text-xs rounded-full border px-2 py-1 text-muted-foreground">
                    已上传 {images.length} 张图片
                  </span>
              </div>

                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                  {images.map((image) => (
                    <div key={image.file_id} className="overflow-hidden rounded-md border bg-muted/30">
                      <div className="aspect-[16/10] bg-background">
                        {resolveApiUrl(image.public_url) ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={resolveApiUrl(image.public_url) ?? ''}
                            alt={image.filename}
                            className="h-full w-full object-cover"
                          />
                        ) : (
                          <div className="flex h-full w-full items-center justify-center text-xs text-muted-foreground">
                            无法预览
                          </div>
                        )}
                      </div>
                      <div className="space-y-0.5 px-2 py-1.5">
                        <div className="text-xs font-medium text-foreground truncate">{image.filename}</div>
                        <div className="text-[10px] text-muted-foreground">
                          {image.mime_type} · {(image.size / 1024).toFixed(1)} KB
                        </div>
                      </div>
                    </div>
                  ))}
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

      {fusionReport && (
        <div className="relative overflow-hidden rounded-2xl border border-slate-200/80 bg-gradient-to-br from-slate-50 via-background to-sky-50/70 p-5 shadow-sm shadow-slate-200/40 dark:border-slate-800 dark:from-slate-950 dark:via-background dark:to-slate-900/80 dark:shadow-black/10">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.12),transparent_38%),radial-gradient(circle_at_bottom_left,rgba(15,23,42,0.06),transparent_32%)] dark:bg-[radial-gradient(circle_at_top_right,rgba(56,189,248,0.18),transparent_32%),radial-gradient(circle_at_bottom_left,rgba(148,163,184,0.12),transparent_30%)]" />
          <div className="relative space-y-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="space-y-1">
                <div className="inline-flex items-center gap-2 rounded-full border border-sky-200/80 bg-white/80 px-3 py-1 text-[11px] font-medium uppercase tracking-[0.18em] text-sky-700 shadow-sm shadow-sky-100/50 dark:border-sky-900/80 dark:bg-slate-950/60 dark:text-sky-300">
                  <Sparkles className="h-3.5 w-3.5" />
                  融合结论
                </div>
                <h2 className="text-lg font-semibold text-foreground">多模态融合摘要</h2>
                <p className="text-sm text-muted-foreground">
                  这是综合报告之后的图文交叉判断，用于补充说明图片输入对整体结论的影响。
                </p>
              </div>
              <div className="inline-flex items-center gap-2 rounded-full border border-slate-200/80 bg-background/80 px-3 py-1.5 text-xs text-muted-foreground shadow-sm dark:border-slate-800 dark:bg-slate-950/60">
                <Layers3 className="h-3.5 w-3.5" />
                报告补充结论
              </div>
            </div>

            <div className="rounded-xl border border-white/70 bg-white/75 p-4 text-sm leading-7 text-slate-700 shadow-inner shadow-white/70 backdrop-blur-sm dark:border-slate-800/80 dark:bg-slate-950/65 dark:text-slate-200 dark:shadow-black/20">
              {fusionReport.fusion_summary}
            </div>

            <div className="flex flex-wrap gap-2">
              <span className="inline-flex items-center rounded-full border border-sky-200/80 bg-sky-50 px-3 py-1 text-xs font-medium text-sky-800 dark:border-sky-900 dark:bg-sky-950/50 dark:text-sky-200">
                一致性：{fusionReport.multimodal_consistency}
              </span>
              <span className="inline-flex items-center rounded-full border border-slate-200/80 bg-slate-100/80 px-3 py-1 text-xs font-medium text-slate-700 dark:border-slate-800 dark:bg-slate-900/70 dark:text-slate-200">
                图像证据：{fusionReport.image_evidence_status}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
