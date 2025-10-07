public class LocalDateGroundTruth {
    public static void main(String[] args) {
        if (args.length != 6) {
            System.err.println("Usage: <year> <month> <day> <perYears> <perMonths> <perDays>");
            System.exit(2);
        }
        try {
            int year = Integer.parseInt(args[0]);
            int month = Integer.parseInt(args[1]);
            int day = Integer.parseInt(args[2]);
            int y = Integer.parseInt(args[3]);
            int m = Integer.parseInt(args[4]);
            int d = Integer.parseInt(args[5]);

            java.time.LocalDate base = java.time.LocalDate.of(year, month, day);
            java.time.Period per = java.time.Period.of(y, m, d);
            java.time.LocalDate res = base.plus(per);

            System.out.printf("%04d-%02d-%02d%n", res.getYear(), res.getMonthValue(), res.getDayOfMonth());
        } catch (Exception e) {
            e.printStackTrace();
            System.exit(1);
        }
    }
}
