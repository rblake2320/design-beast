#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"
#include "BeastEvidenceCollectorLibrary.generated.h"

UCLASS()
class BEASTEVIDENCECOLLECTOR_API UBeastEvidenceCollectorLibrary : public UBlueprintFunctionLibrary
{
    GENERATED_BODY()

public:
    UFUNCTION(BlueprintCallable, Category = "Beast|LiveLink")
    static bool ConnectLiveLinkFaceSource(
        FString SubjectName,
        FString Address,
        int32 Port,
        FString& OutError);

    UFUNCTION(BlueprintCallable, Category = "Beast|Evidence")
    static bool RequestPoseCapture(
        FName SubjectName,
        FName CurveName,
        FString OutputDirectory,
        FString CaptureLabel,
        int32 SampleCount,
        float SampleIntervalSeconds,
        FString& OutError);

    UFUNCTION(BlueprintPure, Category = "Beast|Evidence")
    static bool IsCapturePending();

    UFUNCTION(BlueprintPure, Category = "Beast|Evidence")
    static FString GetLastReceiptPath();

    UFUNCTION(BlueprintPure, Category = "Beast|Evidence")
    static FString GetLastError();
};
