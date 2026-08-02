#include "BeastEvidenceCollectorLibrary.h"

#include "Containers/Ticker.h"
#include "Features/IModularFeatures.h"
#include "GenericPlatform/GenericPlatformMisc.h"
#include "GameFramework/Actor.h"
#include "HAL/FileManager.h"
#include "ILiveLinkClient.h"
#include "ImageUtils.h"
#include "Internationalization/Regex.h"
#include "LiveLinkFaceSourceBlueprint.h"
#include "LiveLinkRole.h"
#include "LiveLinkTypes.h"
#include "LevelEditorViewport.h"
#include "Misc/App.h"
#include "Misc/DateTime.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "PlatformCryptoContextIncludes.h"
#include "Serialization/JsonSerializer.h"
#include "Serialization/JsonWriter.h"
#include "Roles/LiveLinkBasicRole.h"
#include "UnrealClient.h"
#include "Editor.h"

namespace BeastEvidence
{
struct FCurveSample
{
    FString CapturedUtc;
    double PlatformSeconds = 0.0;
    double SourceWorldSeconds = 0.0;
    int32 FrameId = INDEX_NONE;
    float Value = 0.0f;
};

struct FCaptureState
{
    FName Subject;
    FName Curve;
    FString OutputDirectory;
    FString Label;
    FString RunId;
    FString ProjectPath;
    FString ActorPath;
    int32 RequestedSamples = 0;
    TArray<FCurveSample> Samples;
    FString StartedUtc;
    double StartedPlatformSeconds = 0.0;
    double ScreenshotRequestedPlatformSeconds = 0.0;
    FTransform ActorTransform = FTransform::Identity;
    FVector ViewLocation = FVector::ZeroVector;
    FRotator ViewRotation = FRotator::ZeroRotator;
    float ViewFov = 0.0f;
    FString LastError;
    bool bPending = false;
    bool bScreenshotRequested = false;
};

static FCaptureState State;
static FTSTicker::FDelegateHandle TickerHandle;
static FDelegateHandle ScreenshotHandle;
static FString LastReceiptPath;

static bool SampleCurve(FCurveSample& OutSample, FString& OutError)
{
    if (!IModularFeatures::Get().IsModularFeatureAvailable(ILiveLinkClient::ModularFeatureName))
    {
        OutError = TEXT("Live Link client is unavailable");
        return false;
    }
    ILiveLinkClient& Client = IModularFeatures::Get().GetModularFeature<ILiveLinkClient>(
        ILiveLinkClient::ModularFeatureName);
    const TSubclassOf<ULiveLinkRole> SubjectRole = Client.GetSubjectRole_AnyThread(State.Subject);
    if (!SubjectRole)
    {
        OutError = FString::Printf(TEXT("Live Link subject %s has no evaluable role"), *State.Subject.ToString());
        return false;
    }
    FLiveLinkSubjectFrameData Frame;
    if (!Client.EvaluateFrame_AnyThread(State.Subject, SubjectRole, Frame))
    {
        OutError = FString::Printf(
            TEXT("Unable to evaluate Live Link subject %s with role %s"),
            *State.Subject.ToString(),
            *SubjectRole->GetName());
        return false;
    }
    const FLiveLinkBaseStaticData* StaticData = Frame.StaticData.Cast<FLiveLinkBaseStaticData>();
    const FLiveLinkBaseFrameData* FrameData = Frame.FrameData.Cast<FLiveLinkBaseFrameData>();
    if (!StaticData || !FrameData || !StaticData->FindPropertyValue(*FrameData, State.Curve, OutSample.Value))
    {
        FString AvailableProperties;
        if (StaticData)
        {
            const int32 PropertyLimit = FMath::Min(StaticData->PropertyNames.Num(), 40);
            for (int32 Index = 0; Index < PropertyLimit; ++Index)
            {
                if (!AvailableProperties.IsEmpty())
                {
                    AvailableProperties += TEXT(",");
                }
                AvailableProperties += StaticData->PropertyNames[Index].ToString();
            }
        }
        OutError = FString::Printf(
            TEXT("Curve %s is absent from subject %s (role %s; available: %s)"),
            *State.Curve.ToString(),
            *State.Subject.ToString(),
            *SubjectRole->GetName(),
            *AvailableProperties);
        return false;
    }
    OutSample.CapturedUtc = FDateTime::UtcNow().ToIso8601();
    OutSample.PlatformSeconds = FPlatformTime::Seconds();
    OutSample.SourceWorldSeconds = FrameData->WorldTime.GetOffsettedTime();
    OutSample.FrameId = FrameData->FrameId;
    return true;
}

static void ClearPending()
{
    State.bPending = false;
    if (ScreenshotHandle.IsValid())
    {
        FScreenshotRequest::OnScreenshotCaptured().Remove(ScreenshotHandle);
        ScreenshotHandle.Reset();
    }
}

static void OnScreenshotCaptured(int32 Width, int32 Height, const TArray<FColor>& Colors)
{
    FCurveSample FinalSample;
    FString Error;
    if (!SampleCurve(FinalSample, Error))
    {
        State.LastError = Error;
        ClearPending();
        return;
    }
    State.Samples.Add(FinalSample);

    TSet<int32> UniqueFrameIds;
    for (const FCurveSample& Sample : State.Samples)
    {
        UniqueFrameIds.Add(Sample.FrameId);
    }
    const double SourceTimeSpan = State.Samples.Last().SourceWorldSeconds
        - State.Samples[0].SourceWorldSeconds;
    if (UniqueFrameIds.Num() < 3 || SourceTimeSpan < 0.10)
    {
        State.LastError = TEXT("Live Link subject is stale; fewer than three distinct source frames were observed");
        ClearPending();
        return;
    }

    TArray64<uint8> PngBytes;
    FImageUtils::PNGCompressImageArray(Width, Height, Colors, PngBytes);
    const FString ImagePath = FPaths::Combine(State.OutputDirectory, State.Label + TEXT(".png"));
    if (!FFileHelper::SaveArrayToFile(PngBytes, *ImagePath))
    {
        State.LastError = TEXT("Failed to write PNG evidence");
        ClearPending();
        return;
    }

    TArray<uint8> Signature;
    FEncryptionContext Crypto;
    const bool bHashed = PngBytes.Num() <= MAX_int32
        && Crypto.CalcSHA256(
            MakeArrayView(PngBytes.GetData(), static_cast<int32>(PngBytes.Num())),
            Signature)
        && Signature.Num() == 32;

    TSharedRef<FJsonObject> Root = MakeShared<FJsonObject>();
    Root->SetNumberField(TEXT("schema"), 1);
    Root->SetStringField(TEXT("state"), TEXT("POSE_CAPTURED"));
    Root->SetStringField(TEXT("engine_version"), FEngineVersion::Current().ToString());
    Root->SetStringField(TEXT("project"), State.ProjectPath);
    Root->SetStringField(TEXT("run_id"), State.RunId);
    Root->SetStringField(TEXT("subject"), State.Subject.ToString());
    Root->SetStringField(TEXT("curve"), State.Curve.ToString());
    Root->SetStringField(TEXT("capture_label"), State.Label);
    Root->SetStringField(TEXT("started_utc"), State.StartedUtc);
    Root->SetStringField(TEXT("completed_utc"), FDateTime::UtcNow().ToIso8601());
    Root->SetNumberField(TEXT("requested_samples"), State.RequestedSamples);

    TSharedRef<FJsonObject> View = MakeShared<FJsonObject>();
    View->SetNumberField(TEXT("location_x"), State.ViewLocation.X);
    View->SetNumberField(TEXT("location_y"), State.ViewLocation.Y);
    View->SetNumberField(TEXT("location_z"), State.ViewLocation.Z);
    View->SetNumberField(TEXT("rotation_pitch"), State.ViewRotation.Pitch);
    View->SetNumberField(TEXT("rotation_yaw"), State.ViewRotation.Yaw);
    View->SetNumberField(TEXT("rotation_roll"), State.ViewRotation.Roll);
    View->SetNumberField(TEXT("fov"), State.ViewFov);
    Root->SetObjectField(TEXT("editor_view"), View);

    TSharedRef<FJsonObject> Actor = MakeShared<FJsonObject>();
    const FVector ActorLocation = State.ActorTransform.GetLocation();
    const FRotator ActorRotation = State.ActorTransform.Rotator();
    const FVector ActorScale = State.ActorTransform.GetScale3D();
    Actor->SetStringField(TEXT("path"), State.ActorPath);
    Actor->SetNumberField(TEXT("location_x"), ActorLocation.X);
    Actor->SetNumberField(TEXT("location_y"), ActorLocation.Y);
    Actor->SetNumberField(TEXT("location_z"), ActorLocation.Z);
    Actor->SetNumberField(TEXT("rotation_pitch"), ActorRotation.Pitch);
    Actor->SetNumberField(TEXT("rotation_yaw"), ActorRotation.Yaw);
    Actor->SetNumberField(TEXT("rotation_roll"), ActorRotation.Roll);
    Actor->SetNumberField(TEXT("scale_x"), ActorScale.X);
    Actor->SetNumberField(TEXT("scale_y"), ActorScale.Y);
    Actor->SetNumberField(TEXT("scale_z"), ActorScale.Z);
    Root->SetObjectField(TEXT("actor"), Actor);

    TArray<TSharedPtr<FJsonValue>> Samples;
    for (const FCurveSample& Sample : State.Samples)
    {
        TSharedRef<FJsonObject> Item = MakeShared<FJsonObject>();
        Item->SetStringField(TEXT("captured_utc"), Sample.CapturedUtc);
        Item->SetNumberField(TEXT("platform_seconds"), Sample.PlatformSeconds);
        Item->SetNumberField(TEXT("source_world_seconds"), Sample.SourceWorldSeconds);
        Item->SetNumberField(TEXT("frame_id"), Sample.FrameId);
        Item->SetNumberField(TEXT("value"), Sample.Value);
        Samples.Add(MakeShared<FJsonValueObject>(Item));
    }
    Root->SetArrayField(TEXT("samples"), Samples);

    TSharedRef<FJsonObject> Image = MakeShared<FJsonObject>();
    Image->SetStringField(TEXT("path"), ImagePath);
    Image->SetNumberField(TEXT("width"), Width);
    Image->SetNumberField(TEXT("height"), Height);
    Image->SetNumberField(TEXT("byte_count"), static_cast<double>(PngBytes.Num()));
    Image->SetStringField(
        TEXT("sha256"),
        bHashed ? BytesToHex(Signature.GetData(), Signature.Num()).ToLower() : TEXT(""));
    Root->SetObjectField(TEXT("image"), Image);

    FString Json;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&Json);
    FJsonSerializer::Serialize(Root, Writer);
    LastReceiptPath = FPaths::Combine(State.OutputDirectory, State.Label + TEXT(".json"));
    if (!FFileHelper::SaveStringToFile(Json, *LastReceiptPath, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM))
    {
        LastReceiptPath.Reset();
        State.LastError = TEXT("Failed to write JSON evidence receipt");
    }
    ClearPending();
}

static bool TickCapture(float)
{
    if (!State.bPending)
    {
        return false;
    }
    if (State.bScreenshotRequested)
    {
        if (FPlatformTime::Seconds() - State.ScreenshotRequestedPlatformSeconds > 15.0)
        {
            State.LastError = TEXT("Timed out waiting for the Unreal screenshot callback");
            ClearPending();
            return false;
        }
        return true;
    }
    FCurveSample Sample;
    FString Error;
    if (!SampleCurve(Sample, Error))
    {
        State.LastError = Error;
        ClearPending();
        return false;
    }
    State.Samples.Add(Sample);
    if (State.Samples.Num() < State.RequestedSamples - 1)
    {
        return true;
    }

    ScreenshotHandle = FScreenshotRequest::OnScreenshotCaptured().AddStatic(&OnScreenshotCaptured);
    State.bScreenshotRequested = true;
    State.ScreenshotRequestedPlatformSeconds = FPlatformTime::Seconds();
    FScreenshotRequest::RequestScreenshot(false, false);
    return true;
}
}

bool UBeastEvidenceCollectorLibrary::ConnectLiveLinkFaceSource(
    FString SubjectName,
    FString Address,
    int32 Port,
    FString& OutError)
{
    OutError.Reset();
    SubjectName.TrimStartAndEndInline();
    Address.TrimStartAndEndInline();
    if (SubjectName.IsEmpty() || Address.IsEmpty() || Port < 1 || Port > 65535)
    {
        OutError = TEXT("Invalid Live Link Face subject, address, or port");
        return false;
    }

    FLiveLinkSourceHandle SourceHandle;
    bool bCreated = false;
    ULiveLinkFaceSourceBlueprint::CreateLiveLinkFaceSource(SourceHandle, bCreated);
    if (!bCreated)
    {
        OutError = TEXT("UE 5.8 failed to create a native Live Link Face source");
        return false;
    }

    bool bConnected = false;
    ULiveLinkFaceSourceBlueprint::Connect(SourceHandle, SubjectName, Address, bConnected, Port);
    if (!bConnected)
    {
        OutError = FString::Printf(
            TEXT("UE 5.8 Live Link Face source rejected %s:%d for subject %s"),
            *Address,
            Port,
            *SubjectName);
        return false;
    }
    return true;
}

bool UBeastEvidenceCollectorLibrary::RequestPoseCapture(
    FName SubjectName,
    FName CurveName,
    FString OutputDirectory,
    FString CaptureLabel,
    int32 SampleCount,
    float SampleIntervalSeconds,
    FString& OutError)
{
    using namespace BeastEvidence;
    OutError.Reset();
    State.LastError.Reset();
    const auto Reject = [&OutError](const FString& Error)
    {
        OutError = Error;
        State.LastError = Error;
        return false;
    };
    if (State.bPending)
    {
        return Reject(TEXT("Another evidence capture is already pending"));
    }
    const FString SavedProofRoot = FPaths::ConvertRelativePathToFull(
        FPaths::Combine(FPaths::ProjectSavedDir(), TEXT("BeastProof")));
    const FString RunId = FPlatformMisc::GetEnvironmentVariable(TEXT("BEAST_RUN_ID"));
    const FRegexPattern SafeRunId(TEXT("^[A-Za-z0-9_-]{3,40}$"));
    if (!FRegexMatcher(SafeRunId, RunId).FindNext())
    {
        return Reject(TEXT("BEAST_RUN_ID is missing or invalid"));
    }
    const FString ExpectedOutputDirectory = FPaths::ConvertRelativePathToFull(
        FPaths::Combine(SavedProofRoot, RunId, TEXT("deformation")));
    OutputDirectory = FPaths::ConvertRelativePathToFull(OutputDirectory);
    if (!OutputDirectory.Equals(ExpectedOutputDirectory, ESearchCase::IgnoreCase))
    {
        return Reject(TEXT("OutputDirectory must be the active run's Saved/BeastProof/<run-id>/deformation directory"));
    }
    const FRegexPattern SafeLabel(TEXT("^[A-Za-z0-9_-]{3,64}$"));
    if (!FRegexMatcher(SafeLabel, CaptureLabel).FindNext())
    {
        return Reject(TEXT("CaptureLabel must contain only letters, numbers, underscore, or hyphen"));
    }
    if (SubjectName.IsNone() || CurveName.IsNone() || SampleCount < 5 || SampleCount > 120
        || SampleIntervalSeconds < 0.016f || SampleIntervalSeconds > 1.0f)
    {
        return Reject(TEXT("Invalid subject, curve, sample count, or interval"));
    }
    if (!GCurrentLevelEditingViewportClient)
    {
        return Reject(TEXT("No active level-editor viewport is available"));
    }
    const FString BoundReceiptPath = FPaths::Combine(SavedProofRoot, RunId, TEXT("bound-ready.json"));
    FString BoundJson;
    TSharedPtr<FJsonObject> BoundReceipt;
    if (!FFileHelper::LoadFileToString(BoundJson, *BoundReceiptPath))
    {
        return Reject(TEXT("BOUND_READY receipt is missing for the active run"));
    }
    TSharedRef<TJsonReader<>> BoundReader = TJsonReaderFactory<>::Create(BoundJson);
    if (!FJsonSerializer::Deserialize(BoundReader, BoundReceipt) || !BoundReceipt.IsValid()
        || BoundReceipt->GetStringField(TEXT("state")) != TEXT("BOUND_READY")
        || BoundReceipt->GetStringField(TEXT("subject")) != SubjectName.ToString()
        || !FPaths::IsSamePath(
            BoundReceipt->GetStringField(TEXT("project")),
            FPaths::ConvertRelativePathToFull(FPaths::GetProjectFilePath())))
    {
        return Reject(TEXT("BOUND_READY receipt identity does not match this capture request"));
    }
    FString ActorPath;
    if (!BoundReceipt->TryGetStringField(TEXT("actor"), ActorPath))
    {
        return Reject(TEXT("BOUND_READY receipt does not identify the bound actor"));
    }
    AActor* BoundActor = FindObject<AActor>(nullptr, *ActorPath);
    if (!BoundActor)
    {
        return Reject(TEXT("BOUND_READY actor is not loaded in the active proof map"));
    }
    IFileManager::Get().MakeDirectory(*OutputDirectory, true);
    const FString ReceiptPath = FPaths::Combine(OutputDirectory, CaptureLabel + TEXT(".json"));
    const FString ImagePath = FPaths::Combine(OutputDirectory, CaptureLabel + TEXT(".png"));
    if (FPaths::FileExists(ReceiptPath) || FPaths::FileExists(ImagePath))
    {
        return Reject(TEXT("Capture files already exist; use a fresh label"));
    }

    State = FCaptureState();
    State.Subject = SubjectName;
    State.Curve = CurveName;
    State.OutputDirectory = OutputDirectory;
    State.Label = CaptureLabel;
    State.RunId = RunId;
    State.ProjectPath = FPaths::ConvertRelativePathToFull(FPaths::GetProjectFilePath());
    State.ActorPath = ActorPath;
    State.ActorTransform = BoundActor->GetActorTransform();
    State.RequestedSamples = SampleCount;
    State.StartedUtc = FDateTime::UtcNow().ToIso8601();
    State.StartedPlatformSeconds = FPlatformTime::Seconds();
    State.ViewLocation = GCurrentLevelEditingViewportClient->GetViewLocation();
    State.ViewRotation = GCurrentLevelEditingViewportClient->GetViewRotation();
    State.ViewFov = GCurrentLevelEditingViewportClient->ViewFOV;
    State.bPending = true;
    LastReceiptPath.Reset();
    TickerHandle = FTSTicker::GetCoreTicker().AddTicker(
        FTickerDelegate::CreateStatic(&TickCapture), SampleIntervalSeconds);
    return true;
}

bool UBeastEvidenceCollectorLibrary::IsCapturePending()
{
    return BeastEvidence::State.bPending;
}

FString UBeastEvidenceCollectorLibrary::GetLastReceiptPath()
{
    return BeastEvidence::LastReceiptPath;
}

FString UBeastEvidenceCollectorLibrary::GetLastError()
{
    return BeastEvidence::State.LastError;
}
