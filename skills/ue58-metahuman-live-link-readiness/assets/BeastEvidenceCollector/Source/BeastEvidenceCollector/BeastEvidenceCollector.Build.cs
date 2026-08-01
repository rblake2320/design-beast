using UnrealBuildTool;

public class BeastEvidenceCollector : ModuleRules
{
    public BeastEvidenceCollector(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[] { "Core", "CoreUObject", "Engine" });
        PrivateDependencyModuleNames.AddRange(new[] { "LiveLinkInterface", "Json", "UnrealEd" });
    }
}
