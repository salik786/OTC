using System.Text.RegularExpressions;

namespace Otc.VR
{
    public enum SafetyLevel { None, SeePharmacist, Emergency }

    /// <summary>
    /// Flags questions that should go to a person rather than (only) to the leaflet assistant. This is a
    /// conservative keyword screen on the transcript - it can only add a safety prompt, never suppress an
    /// answer, and it does not replace clinical judgement. English phrases only for now; other languages
    /// still get the backend's own out-of-scope deflection.
    /// </summary>
    public static class SafetyCheck
    {
        static readonly Regex Emergency = new Regex(
            @"\b(chest pain|heart attack|stroke|can'?t breathe|cannot breathe|difficulty breathing|struggling to breathe|" +
            @"short(ness)? of breath|overdose|overdosed|took too many|taken too many|took too much|taken too much|" +
            @"swallowed (a|the|some)|poison(ed|ing)?|suicid\w*|kill myself|end my life|self[- ]harm|hurt myself|" +
            @"unconscious|passed out|fainted|seizure|fitting|anaphyla\w*|allergic reaction|" +
            @"(swollen|swelling).{0,20}(face|lips?|tongue|throat)|severe bleeding|coughing (up )?blood|vomiting blood)\b",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        static readonly Regex SeePharmacist = new Regex(
            @"\b(pregnan\w*|breast ?feeding|my baby|newborn|infant|toddler|under (2|two|6|six)|" +
            @"kidney (disease|problems?)|liver (disease|problems?)|blood thinners?|warfarin|" +
            @"other medicines?|other medications?|mix(ing)? with alcohol)\b",
            RegexOptions.IgnoreCase | RegexOptions.Compiled);

        public static SafetyLevel Assess(string text)
        {
            if (string.IsNullOrWhiteSpace(text)) return SafetyLevel.None;
            if (Emergency.IsMatch(text)) return SafetyLevel.Emergency;
            if (SeePharmacist.IsMatch(text)) return SafetyLevel.SeePharmacist;
            return SafetyLevel.None;
        }

        // Australian services (the study runs at Western Sydney University).
        public const string EmergencyTitle = "This could be urgent";
        public const string EmergencyBody =
            "If someone is in danger or very unwell, call <b>000</b> now.\n\n" +
            "Poisons Information Centre (24/7): <b>13 11 26</b>\n" +
            "healthdirect nurse line (24/7): <b>1800 022 222</b>\n\n" +
            "Please also tell a pharmacist straight away.";
        public const string EmergencySpoken =
            "This sounds like it could be urgent. If someone is in danger or very unwell, please call triple zero now, " +
            "or the Poisons Information Centre on 13 11 26. Please also tell a pharmacist straight away.";

        public const string PharmacistTitle = "Please check with a pharmacist";
        public const string PharmacistBody =
            "Your question involves something that needs personal advice (for example pregnancy, young children, " +
            "other medicines or a health condition).\n\nA pharmacist can check what is safe for you.";
    }
}
