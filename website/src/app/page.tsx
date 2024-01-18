import MaxWidthWrapper from "@/components/MaxWidthWrapper"


export default function Home() {
  return (
    <>
      {/* <MaxWidthWrapper className='mb-12 mt-12 sm:mt-40 flex flex-col items-center justify-center text-center'> */}
      <MaxWidthWrapper className='mx-auto mb-12 pt-16 sm:mt-40 flex flex-col items-center justify-center text-center'>
          <h1 className="max-w-4xl text-5xl - font-bold md:text-6xl lg:text-7xl">
            Record a voice memo. Send it as a <span className="text-orange-600">letter</span>.
          </h1>
          <p className="mt-5 max-w-prose text-zinc-700 sm:text-lg">Effortlessly create and send physical letters from your telegram and whatsapp chat - simply record, edit, and mail, all without leaving the chat.</p>
          <div className='mx-auto mt-4 mb-4 flex max-w-fit items-center justify-center space-x-2 overflow-hidden rounded-full border border-gray-200 bg-white px-7 py-2 shadow-md backdrop-blur transition-all hover:border-gray-300 hover:bg-white/50'>
            <p className='text-sm font-semibold text-gray-700'>
              GrannyMail is currently in closed alpha.
            </p>
          </div>
          {/* <Link href="/dashboard" target="_blank" className={buttonVariants({ size: "lg", className: "mt-5", variant: "outline" })}>Join Waitlist <ArrowRight className="ml-2 h-4 w-5" /></Link> */}
      </MaxWidthWrapper>

      {/* Value proposition section */}
      <div>
        <div className="relative isolate">
          <div aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 -top-30 -z-10 transform-gpu overflow-hideen blur-3xl sm:-top-80">
            <div
              style={{
                clipPath:
                'polygon(74.1% 44.1%, 100% 61.6%, 97.5% 26.9%, 85.5% 0.1%, 80.7% 2%, 72.5% 32.5%, 60.2% 62.4%, 52.4% 68.1%, 47.5% 58.3%, 45.2% 34.5%, 27.5% 76.7%, 0.1% 64.9%, 17.9% 100%, 27.6% 76.8%, 76.1% 97.7%, 74.1% 44.1%)',}}
              className="relative left-[calc(50%-11rem)] aspect-[1155/678] w-[36.125rem] -translate-x-1/2 rotate-[30deg] bg-gradient-to-tr from-[#ff80b5] to-[#9089fc] opacity-30 sm:left-[calc(50%-30rem)] sm:w-[72.1875rem]" />
          </div>
        </div>
      </div>
    </>
  )
}
